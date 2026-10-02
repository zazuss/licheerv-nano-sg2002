"""LicheeRV Nano client: three active-low GPIO buttons and onboard microphone.

Uses only Python standard library plus ALSA's arecord, already present in the
documented board image. Run as root to export/read sysfs GPIO.
"""

from __future__ import annotations

import argparse
import json
import queue
import signal
import os
import struct
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GPIO_ROOT = Path("/sys/class/gpio")
EV_KEY = 0x01
USER_KEY_CODE = 431  # Actual onboard USER key code on this LicheeRV Nano image.


class GPIOButton:
    def __init__(self, number: int):
        self.number = number
        self.path = GPIO_ROOT / f"gpio{number}"
        if not self.path.exists():
            (GPIO_ROOT / "export").write_text(str(number))
            for _ in range(20):
                if self.path.exists():
                    break
                time.sleep(0.05)
        if not self.path.exists():
            raise RuntimeError(f"无法导出 GPIO {number}")
        (self.path / "direction").write_text("in")

    def pressed(self) -> bool:
        return (self.path / "value").read_text().strip() == "0"


class Sender:
    def __init__(self, config: dict):
        self.url = config["server_url"].rstrip("/")
        self.token = config["token"]
        self.jobs = queue.Queue(maxsize=10)
        threading.Thread(target=self._worker, daemon=True).start()

    def send(self, route: str, data: bytes, content_type: str):
        try:
            self.jobs.put_nowait((route, data, content_type, uuid.uuid4().hex))
        except queue.Full:
            print("发送队列已满，事件已丢弃", flush=True)

    def _worker(self):
        while True:
            route, data, content_type, event_id = self.jobs.get()
            try:
                for attempt in range(3):
                    request = urllib.request.Request(
                        self.url + route, data=data, method="POST",
                        headers={
                            "Content-Type": content_type,
                            "X-Bridge-Token": self.token,
                            "X-Event-Id": event_id,
                        },
                    )
                    try:
                        with urllib.request.urlopen(request, timeout=60) as response:
                            print(response.read().decode("utf-8"), flush=True)
                        break
                    except urllib.error.HTTPError as exc:
                        print(f"服务器拒绝 {route}: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}", flush=True)
                        break
                    except (urllib.error.URLError, TimeoutError) as exc:
                        print(f"发送失败 ({attempt + 1}/3): {exc}", flush=True)
                        time.sleep(1 + attempt)
            finally:
                self.jobs.task_done()


class Recorder:
    def __init__(self, config: dict, sender: Sender):
        self.config = config
        self.sender = sender
        self.process = None
        self.path = None

    def start(self):
        if self.process is not None:
            return
        mixer = self.config.get("audio_mixer_device", "hw:0")
        volume = str(self.config.get("capture_volume", 16))
        # The stock Nano image leaves the ADC power switch off after boot.
        for control, value in (("numid=1", "on,on"), ("numid=3", "off,off"),
                               ("numid=2", f"{volume},{volume}")):
            subprocess.run(["amixer", "-D", mixer, "cset", control, value],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=False)
        with tempfile.NamedTemporaryFile(prefix="codex_voice_", suffix=".wav", delete=False) as f:
            self.path = Path(f.name)
        command = [
            "arecord", "-D", self.config.get("audio_device", "hw:0,0"),
            "-f", "S16_LE", "-r", str(self.config.get("audio_rate", 48000)),
            "-c", "1", "-t", "wav", "-d", str(self.config.get("max_record_seconds", 20)),
            str(self.path),
        ]
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("开始录音；松开第三个按钮后发送", flush=True)
        except Exception:
            self.path.unlink(missing_ok=True)
            self.path = None
            raise

    def stop(self):
        if self.process is None:
            return
        proc, path = self.process, self.path
        self.process, self.path = None, None
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        try:
            data = path.read_bytes()
            if len(data) > 4096:
                if self.config.get("keep_last_recording", False):
                    Path(self.config.get("last_recording_path", "/tmp/codex_last_voice.wav")).write_bytes(data)
                self.sender.send("/audio", data, "audio/wav")
                print(f"录音发送队列：{len(data)} 字节", flush=True)
            else:
                print("录音过短或失败，未发送", flush=True)
        finally:
            path.unlink(missing_ok=True)


class UserKeyVoice:
    """Use the LicheeRV Nano USER key as a press-to-talk key."""
    event_struct = struct.Struct("@llHHi")  # Linux input_event on 64-bit RISC-V.

    def __init__(self, config: dict, sender: Sender):
        self.device = config.get("user_key_event", "/dev/input/event0")
        self.key_code = int(config.get("user_key_code", USER_KEY_CODE))
        self.recorder = Recorder(config, sender)

    def run(self):
        print(f"监听 USER 语音键 {self.device}（按住说话、松开发送）", flush=True)
        fd = os.open(self.device, os.O_RDONLY)
        pending = b""
        try:
            while True:
                pending += os.read(fd, self.event_struct.size * 16)
                while len(pending) >= self.event_struct.size:
                    raw, pending = pending[:self.event_struct.size], pending[self.event_struct.size:]
                    _, _, event_type, code, value = self.event_struct.unpack(raw)
                    if event_type != EV_KEY or code != self.key_code:
                        continue
                    if value == 1:
                        self.recorder.start()
                    elif value == 0:
                        self.recorder.stop()
        except KeyboardInterrupt:
            pass
        finally:
            os.close(fd)
            self.recorder.stop()


def run_gpio(config: dict, sender: Sender):
    numbers = config["gpio"]
    if any(not isinstance(numbers.get(name), int) for name in ("approve", "deny", "talk")):
        raise SystemExit("请先在 board_config.json 填入三个 sysfs GPIO 全局编号")
    if len(set(numbers.values())) != 3:
        raise SystemExit("三个按钮必须使用不同 GPIO")
    buttons = {name: GPIOButton(numbers[name]) for name in ("approve", "deny", "talk")}
    recorder = Recorder(config, sender)
    stable = {name: button.pressed() for name, button in buttons.items()}
    raw = stable.copy()
    changed_at = {name: time.monotonic() for name in buttons}
    print("监听按钮中；Ctrl+C 退出", flush=True)
    try:
        while True:
            now = time.monotonic()
            for name, button in buttons.items():
                current = button.pressed()
                if current != raw[name]:
                    raw[name] = current
                    changed_at[name] = now
                if raw[name] != stable[name] and now - changed_at[name] >= 0.05:
                    stable[name] = raw[name]
                    if name == "talk":
                        if stable[name]:
                            recorder.start()
                        else:
                            recorder.stop()
                    elif stable[name]:
                        sender.send("/event", json.dumps({"button": name}).encode(), "application/json")
                        print(f"按下 {name}", flush=True)
            time.sleep(0.02)
    except KeyboardInterrupt:
        recorder.stop()


def run_simulation(sender: Sender):
    print("模拟模式：输入 1=同意/发送，2=拒绝/停止，3 <wav路径>=上传录音，q=退出")
    while True:
        try:
            command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if command == "q":
            break
        if command in ("1", "2"):
            kind = "approve" if command == "1" else "deny"
            sender.send("/event", json.dumps({"button": kind}).encode(), "application/json")
        elif command.startswith("3 "):
            path = Path(command[2:].strip().strip('"'))
            if path.is_file():
                sender.send("/audio", path.read_bytes(), "audio/wav")
            else:
                print("WAV 文件不存在")
        else:
            print("未知命令")
    sender.jobs.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "board_config.json"))
    parser.add_argument("--simulate", action="store_true", help="无需 GPIO，可在电脑上测试网络")
    parser.add_argument("--user-key-voice", action="store_true",
                        help="用板载 USER 键进行按住说话")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if len(config.get("token", "")) < 24 or config["token"].startswith("PASTE_"):
        raise SystemExit("请将 pc_config.json 中的 token 填入 board_config.json")
    sender = Sender(config)
    if args.simulate:
        run_simulation(sender)
    elif args.user_key_voice:
        UserKeyVoice(config, sender).run()
    else:
        run_gpio(config, sender)


if __name__ == "__main__":
    main()
