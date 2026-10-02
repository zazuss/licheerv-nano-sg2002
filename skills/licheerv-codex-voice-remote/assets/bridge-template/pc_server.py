"""LAN receiver for LicheeRV Nano button and WAV messages (Windows PC)."""

from __future__ import annotations

import argparse
import array
import hmac
import io
import json
import re
import threading
import time
import wave
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from codex_desktop import CodexDesktop

ROOT = Path(__file__).resolve().parent
MAX_AUDIO_BYTES = 10 * 1024 * 1024


def voice_command(text: str) -> str | None:
    """Return an explicit hands-free command, if the utterance is only a command."""
    normalized = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE).casefold()
    return {
        "开始": "send",
        "取消": "clear",
    }.get(normalized)


PAGE = """<!doctype html><html lang=zh><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>荔枝派 Codex 遥控器</title>
<style>body{font:16px system-ui;margin:2rem auto;max-width:850px;padding:0 1rem;background:#111827;color:#e5e7eb}
h1{font-size:1.5rem}pre{white-space:pre-wrap;background:#1f2937;padding:1rem;border-radius:.5rem}
.box{background:#1f2937;padding:1rem;border-radius:.5rem;margin:1rem 0}small{color:#9ca3af}</style>
<h1>荔枝派 Codex 遥控器</h1><small>语音会优先写入唯一可见的 Codex 窗口；按钮操作只在 Codex 位于前台时执行。</small>
<div class=box><b>最新语音</b><pre id=transcript>等待中</pre></div>
<div class=box><b>事件</b><pre id=events>等待中</pre></div>
<script>async function refresh(){try{let r=await fetch('/api/state');let x=await r.json();
document.getElementById('transcript').textContent=x.transcript||'尚无识别结果';
document.getElementById('events').textContent=x.events.map(e=>e.time+'  '+e.message).join('\n')||'尚无事件';
}catch(e){document.getElementById('events').textContent=String(e)}}refresh();setInterval(refresh,1500)</script></html>"""


class BridgeState:
    def __init__(self, config: dict):
        self.config = config
        self.adapter = CodexDesktop(config)
        self.lock = threading.Lock()
        self.model_lock = threading.Lock()
        self.sensevoice = None
        self.events = deque(maxlen=50)
        self.seen = deque(maxlen=200)
        self.transcript = ""

    def log(self, message: str):
        row = {"time": time.strftime("%H:%M:%S"), "message": message}
        with self.lock:
            self.events.appendleft(row)
        print(f"[{row['time']}] {message}", flush=True)

    def accept_id(self, event_id: str) -> bool:
        with self.lock:
            if event_id in self.seen:
                return False
            self.seen.append(event_id)
            return True

    def snapshot(self) -> dict:
        with self.lock:
            return {"transcript": self.transcript, "events": list(self.events)}

    def signal_reachy(self, action: str) -> None:
        """Forward LicheeRV voice lifecycle states to the local Reachy bridge."""
        url = self.config.get("reachy_bridge_url", "").rstrip("/")
        token = self.config.get("reachy_bridge_token", "")
        if not url or not token:
            return

        def send() -> None:
            try:
                request = urllib.request.Request(
                    url + "/command",
                    data=json.dumps({"action": action}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-Reachy-Token": token},
                    method="POST",
                )
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=1.5):
                    pass
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self.log(f"Reachy 桥接不可达：{exc}")

        threading.Thread(target=send, daemon=True).start()

    def _transcribe_sensevoice(self, wav_data: bytes) -> str:
        """Run the compact Mandarin-oriented offline SenseVoice model on CPU."""
        import sherpa_onnx

        root = ROOT / "models" / "sensevoice" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
        with self.model_lock:
            if self.sensevoice is None:
                model = root / "model.int8.onnx"
                tokens = root / "tokens.txt"
                if not model.is_file() or not tokens.is_file():
                    raise RuntimeError("SenseVoice 模型不完整；请运行 setup_pc.ps1 安装并下载模型")
                self.log("正在加载 SenseVoice 中文语音模型")
                self.sensevoice = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                    model=str(model), tokens=str(tokens), language="zh", use_itn=True,
                    provider="cpu", num_threads=int(self.config.get("sensevoice_threads", 4)),
                )
            with wave.open(io.BytesIO(wav_data), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                    raise ValueError("只支持 16 位单声道 WAV")
                pcm = array.array("h")
                pcm.frombytes(wav.readframes(wav.getnframes()))
                stream = self.sensevoice.create_stream()
                stream.accept_waveform(wav.getframerate(), pcm)
            self.sensevoice.decode_stream(stream)
            return stream.result.text.strip()

    def transcribe(self, wav_data: bytes) -> str:
        return self._transcribe_sensevoice(wav_data)


def validate_wav(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise ValueError("需要单声道 16 位 PCM WAV")
            if w.getframerate() not in (16000, 48000):
                raise ValueError("采样率需为 16 kHz 或 48 kHz")
            duration = w.getnframes() / w.getframerate()
            if duration < 0.2 or duration > 30:
                raise ValueError("录音时长需为 0.2–30 秒")
            return duration
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"无效 WAV：{exc}") from exc


def make_handler(state: BridgeState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def respond(self, status: int, data: dict):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self.respond(200, {"ok": True})
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                return self.respond(403, {"error": "面板仅允许本机访问"})
            if self.path == "/api/state":
                return self.respond(200, state.snapshot())
            if self.path == "/":
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            self.respond(404, {"error": "not found"})

        def do_POST(self):
            token = self.headers.get("X-Bridge-Token", "")
            if not hmac.compare_digest(token, state.config["token"]):
                return self.respond(401, {"error": "认证失败"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.respond(400, {"error": "无效 Content-Length"})
            if size <= 0 or size > MAX_AUDIO_BYTES:
                return self.respond(413, {"error": "请求体大小无效"})
            body = self.rfile.read(size)
            event_id = self.headers.get("X-Event-Id", "")
            if not event_id or len(event_id) > 100:
                return self.respond(400, {"error": "缺少 X-Event-Id"})
            if self.path == "/event":
                try:
                    obj = json.loads(body)
                    kind = obj["button"]
                    if kind not in ("approve", "deny"):
                        raise ValueError("未知按钮")
                except (ValueError, KeyError, UnicodeDecodeError):
                    return self.respond(400, {"error": "无效按钮事件"})
                if not state.accept_id(event_id):
                    return self.respond(200, {"ok": True, "duplicate": True})
                state.signal_reachy("acknowledge" if kind == "approve" else "neutral")
                result = state.adapter.handle_button(kind)
                state.log(f"{kind}: {result}")
                return self.respond(200, {"ok": True, "result": result})
            if self.path == "/audio":
                try:
                    duration = validate_wav(body)
                except ValueError as exc:
                    return self.respond(400, {"error": str(exc)})
                if not state.accept_id(event_id):
                    return self.respond(200, {"ok": True, "duplicate": True})
                state.signal_reachy("listening")
                state.log(f"收到录音 {duration:.1f} 秒，正在识别")
                try:
                    text = state.transcribe(body)
                except Exception as exc:
                    state.log(f"识别失败：{exc}")
                    return self.respond(500, {"error": "识别失败，见电脑端日志"})
                with state.lock:
                    state.transcript = text
                state.signal_reachy("thinking")
                command = voice_command(text)
                if command == "send":
                    state.signal_reachy("acknowledge")
                    result = state.adapter.send_current_input()
                elif command == "clear":
                    state.signal_reachy("neutral")
                    result = state.adapter.clear_current_input()
                else:
                    result = state.adapter.insert_text(text) if text else "未识别到语音"
                state.log(f"语音：{text or '(空)'}；{result}")
                return self.respond(200, {"ok": True, "text": text, "command": command, "result": result})
            self.respond(404, {"error": "not found"})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "pc_config.json"))
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if len(config.get("token", "")) < 24 or "CHANGE_ME" in config["token"]:
        raise SystemExit("请先运行 setup_pc.ps1，生成至少 24 字符的随机 token")
    state = BridgeState(config)
    server = ThreadingHTTPServer((config["listen_host"], int(config["port"])), make_handler(state))
    print(f"监听 {config['listen_host']}:{config['port']}；本机面板 http://127.0.0.1:{config['port']}/")
    print("电脑与开发板需在同一局域网；语音会优先输入唯一可见的 Codex 窗口")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
