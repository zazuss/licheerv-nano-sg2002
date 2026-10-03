"""Local protocol checks; no network outside localhost or speech model needed."""

import io
import json
import threading
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer

from board_client import Sender
from codex_desktop import CodexDesktop
from pc_server import BridgeState, make_handler, voice_command


class FakeCodex:
    def __init__(self):
        self.buttons = []
        self.texts = []
        self.sends = 0
        self.clears = 0

    def handle_button(self, kind):
        self.buttons.append(kind)
        return "mock button"

    def insert_text(self, text):
        self.texts.append(text)
        return "mock paste"

    def send_current_input(self):
        self.sends += 1
        return "mock send"

    def clear_current_input(self):
        self.clears += 1
        return "mock clear"


class BridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = {
            "token": "01234567890123456789012345678901",
            "button_labels": {"approve": [], "deny": [], "send": [], "stop": []},
            "composer_labels": [],
        }
        cls.state = BridgeState(config)
        cls.fake = FakeCodex()
        cls.state.adapter = cls.fake
        cls.state.transcribe = lambda _: "测试语音"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.state))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def post(self, route, data, event_id, token=None):
        req = urllib.request.Request(
            self.base + route, data=data, method="POST",
            headers={"X-Event-Id": event_id, "X-Bridge-Token": token or self.state.config["token"]},
        )
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def test_button_authentication_and_deduplication(self):
        body = b'{"button":"approve"}'
        before = len(self.fake.buttons)
        status, _ = self.post("/event", body, "button-1", token="wrong")
        self.assertEqual(status, 401)
        status, _ = self.post("/event", body, "button-1")
        self.assertEqual(status, 200)
        status, reply = self.post("/event", body, "button-1")
        self.assertTrue(reply["duplicate"])
        self.assertEqual(self.fake.buttons[before:], ["approve"])

    def test_audio_packet(self):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(b"\0\0" * 48000)
        status, reply = self.post("/audio", buf.getvalue(), "audio-1")
        self.assertEqual(status, 200)
        self.assertEqual(reply["text"], "测试语音")
        self.assertEqual(self.fake.texts, ["测试语音"])
        status, _ = self.post("/audio", b"garbage", "audio-bad")
        self.assertEqual(status, 400)

    def test_voice_commands(self):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(b"\0\0" * 48000)
        self.state.transcribe = lambda _: "开始。"
        status, reply = self.post("/audio", buf.getvalue(), "audio-send")
        self.assertEqual(status, 200)
        self.assertEqual(reply["command"], "send")
        self.assertEqual(self.fake.sends, 1)
        self.state.transcribe = lambda _: "取消"
        status, reply = self.post("/audio", buf.getvalue(), "audio-clear")
        self.assertEqual(status, 200)
        self.assertEqual(reply["command"], "clear")
        self.assertEqual(self.fake.clears, 1)
        self.assertIsNone(voice_command("开始写代码"))

    def test_active_task_submit_uses_composer_shortcut(self):
        adapter = CodexDesktop({
            "button_labels": {"approve": [], "deny": [], "send": ["Send"], "stop": ["Stop"]},
            "composer_labels": ["message"],
            "send_shortcut": "{ENTER}",
        })
        composer = Mock()
        window = Mock()
        with patch("codex_desktop.com_context", return_value=nullcontext()), \
             patch.object(adapter, "_voice_window", return_value=window), \
             patch.object(adapter, "_composer", return_value=composer), \
             patch("pywinauto.keyboard.send_keys") as send_keys:
            result = adapter.send_current_input()

        self.assertEqual(result, "已从 Codex 输入框提交消息；未停止当前任务")
        composer.click_input.assert_called_once_with()
        send_keys.assert_called_once_with("{ENTER}")

    def test_composer_prefers_unique_prosemirror_over_other_edit(self):
        adapter = CodexDesktop({
            "button_labels": {}, "composer_labels": ["message", "ask"],
        })
        search = Mock()
        search.is_visible.return_value = True
        search.is_enabled.return_value = True
        search.element_info.class_name = "SearchBox"
        search.element_info.name = "Ask search"
        composer = Mock()
        composer.is_visible.return_value = True
        composer.is_enabled.return_value = True
        composer.element_info.class_name = "ProseMirror ProseMirror-focused"
        composer.element_info.name = "使用 ChatGPT Work"
        window = Mock()
        window.descendants.return_value = [search, composer]

        self.assertIs(adapter._composer(window), composer)

    def test_composer_retries_transient_duplicate(self):
        adapter = CodexDesktop({"button_labels": {}, "composer_labels": []})
        composer = Mock()
        composer.is_visible.return_value = True
        composer.is_enabled.return_value = True
        composer.element_info.class_name = "ProseMirror"
        composer.element_info.name = "使用 ChatGPT Work"
        duplicate = Mock()
        duplicate.is_visible.return_value = True
        duplicate.is_enabled.return_value = True
        duplicate.element_info.class_name = "ProseMirror"
        duplicate.element_info.name = "使用 ChatGPT Work"
        window = Mock()
        window.descendants.side_effect = [[composer, duplicate], [composer]]

        with patch("codex_desktop.time.sleep") as sleep:
            self.assertIs(adapter._composer(window), composer)
        sleep.assert_called_once_with(0.2)

    def test_composer_prefers_question_reply_over_general_work_input(self):
        adapter = CodexDesktop({"button_labels": {}, "composer_labels": ["ask"]})
        reply = Mock()
        reply.is_visible.return_value = True
        reply.is_enabled.return_value = True
        reply.element_info.class_name = "ProseMirror"
        reply.element_info.name = "回复…"
        general = Mock()
        general.is_visible.return_value = True
        general.is_enabled.return_value = True
        general.element_info.class_name = "ProseMirror"
        general.element_info.name = "使用 ChatGPT Work"
        window = Mock()
        window.descendants.return_value = [reply, general]

        self.assertIs(adapter._composer(window), reply)


    def test_board_sender_to_pc_receiver(self):
        sender = Sender({"server_url": self.base, "token": self.state.config["token"]})
        sender.send("/event", b'{"button":"deny"}', "application/json")
        sender.jobs.join()
        self.assertEqual(self.fake.buttons[-1], "deny")


if __name__ == "__main__":
    unittest.main()
