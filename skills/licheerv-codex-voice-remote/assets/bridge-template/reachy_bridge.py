"""Safe local command bridge for a Reachy Mini controlled by Codex."""

from __future__ import annotations

import argparse
import hmac
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class ReachyController:
    """Allowlisted expressive motions; dry-run by default until a robot is configured."""

    def __init__(self, config: dict):
        self.config = config
        self.lock = threading.Lock()
        self.last_action = "idle"
        self.last_error = None

    def snapshot(self) -> dict:
        return {
            "ok": self.last_error is None,
            "mode": self.config.get("mode", "dry_run"),
            "last_action": self.last_action,
            "last_error": self.last_error,
        }

    def _robot(self):
        from reachy_mini import ReachyMini

        return ReachyMini(
            host=self.config.get("robot_host", "reachy-mini.local"),
            port=int(self.config.get("robot_port", 8000)),
            connection_mode=self.config.get("connection_mode", "network"),
            media_backend="no_media",
        )

    @staticmethod
    def _clamp(value, low, high) -> float:
        return max(low, min(high, float(value)))

    def execute(self, command: dict) -> dict:
        action = command.get("action")
        allowed = {"listening", "thinking", "acknowledge", "neutral", "look", "wake", "sleep"}
        if action not in allowed:
            raise ValueError(f"不允许的 Reachy 动作：{action}")
        with self.lock:
            self.last_action = action
            self.last_error = None
            if self.config.get("mode", "dry_run") == "dry_run":
                return {"ok": True, "mode": "dry_run", "action": action}
            try:
                from reachy_mini.utils import create_head_pose

                with self._robot() as mini:
                    if action == "listening":
                        mini.goto_target(antennas=[0.25, -0.25], duration=0.35, method="minjerk")
                    elif action == "thinking":
                        mini.goto_target(antennas=[0.15, 0.15], duration=0.35, method="cartoon")
                    elif action == "acknowledge":
                        mini.goto_target(antennas=[0.5, -0.5], duration=0.25, method="minjerk")
                        mini.goto_target(antennas=[-0.5, 0.5], duration=0.25, method="minjerk")
                        mini.goto_target(antennas=[0, 0], duration=0.35, method="minjerk")
                    elif action == "neutral":
                        mini.goto_target(head=create_head_pose(), antennas=[0, 0], duration=0.6, method="minjerk")
                    elif action == "look":
                        yaw = self._clamp(command.get("yaw", 0), -30, 30)
                        pitch = self._clamp(command.get("pitch", 0), -20, 20)
                        mini.goto_target(head=create_head_pose(yaw=yaw, pitch=pitch, degrees=True), duration=0.6, method="minjerk")
                    elif action == "wake":
                        mini.wake_up()
                    elif action == "sleep":
                        mini.goto_sleep()
                return {"ok": True, "mode": "robot", "action": action}
            except Exception as exc:
                self.last_error = str(exc)
                raise


def make_handler(controller: ReachyController):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            return

        def reply(self, status: int, data: dict):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                return self.reply(200, controller.snapshot())
            self.reply(404, {"error": "not found"})

        def do_POST(self):
            token = self.headers.get("X-Reachy-Token", "")
            if not hmac.compare_digest(token, controller.config["token"]):
                return self.reply(401, {"error": "认证失败"})
            if self.path != "/command":
                return self.reply(404, {"error": "not found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                command = json.loads(self.rfile.read(size))
                return self.reply(200, controller.execute(command))
            except (ValueError, json.JSONDecodeError) as exc:
                return self.reply(400, {"error": str(exc)})
            except Exception as exc:
                return self.reply(502, {"error": f"Reachy 执行失败：{exc}"})

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "reachy_config.json"))
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if len(config.get("token", "")) < 24 or "CHANGE_ME" in config["token"]:
        raise SystemExit("请先配置 reachy_config.json 的 token")
    server = ThreadingHTTPServer((config.get("listen_host", "127.0.0.1"), int(config.get("port", 8766))), make_handler(ReachyController(config)))
    print(f"Reachy bridge: http://127.0.0.1:{server.server_port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
