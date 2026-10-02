"""Best-effort Windows UI Automation adapter for Codex desktop.

No private Codex protocol is used. A button is clicked only when exactly one
visible, enabled control has a configured accessible name.
"""

from __future__ import annotations

import time
from contextlib import contextmanager


@contextmanager
def com_context():
    import pythoncom

    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


class CodexDesktop:
    def __init__(self, config: dict):
        self.labels = config["button_labels"]
        self.composer_labels = [x.casefold() for x in config["composer_labels"]]
        # Enter is the Codex composer submission key. It remains available when
        # an active task replaces the visible Send button with Stop.
        self.send_shortcut = config.get("send_shortcut", "{ENTER}")

    def _window(self):
        import psutil
        import win32gui
        import win32process
        from pywinauto import Desktop

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            raise RuntimeError("没有前台窗口")
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        exe = proc.exe().lower()
        if "openai.codex_" not in exe or proc.name().lower() != "chatgpt.exe":
            raise RuntimeError("请先把 Codex 桌面窗口置于前台")
        return Desktop(backend="uia").window(handle=hwnd)

    @staticmethod
    def _is_codex_window(hwnd) -> bool:
        import psutil
        import win32gui
        import win32process

        if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return False
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            return (
                proc.name().lower() == "chatgpt.exe"
                and "openai.codex_" in proc.exe().lower()
            )
        except (psutil.Error, OSError):
            return False

    def _voice_window(self):
        """Use the foreground Codex window, or focus the only visible one."""
        import win32gui
        from pywinauto import Desktop

        foreground = win32gui.GetForegroundWindow()
        if foreground and self._is_codex_window(foreground):
            return Desktop(backend="uia").window(handle=foreground)

        handles = []

        def collect(hwnd, _):
            if self._is_codex_window(hwnd):
                handles.append(hwnd)

        win32gui.EnumWindows(collect, None)
        if not handles:
            raise RuntimeError("没有可见的 Codex 窗口")
        if len(handles) > 1:
            raise RuntimeError("检测到多个 Codex 窗口；请先将目标窗口置于前台")
        window = Desktop(backend="uia").window(handle=handles[0])
        window.set_focus()
        time.sleep(0.1)
        if win32gui.GetForegroundWindow() != handles[0]:
            raise RuntimeError("无法聚焦 Codex 窗口")
        return window

    @staticmethod
    def _visible_enabled(control) -> bool:
        try:
            return control.is_visible() and control.is_enabled()
        except Exception:
            return False

    def _find_button(self, window, names):
        buttons = window.descendants(control_type="Button")
        for name in names:
            matches = [
                b for b in buttons
                if self._visible_enabled(b) and b.window_text().strip().casefold() == name.casefold()
            ]
            if len(matches) == 1:
                return matches[0], name
            if len(matches) > 1:
                raise RuntimeError(f"找到多个同名按钮：{name}，已跳过")
        return None, None

    def _composer(self, window):
        for attempt in range(3):
            edits = [e for e in window.descendants(control_type="Edit") if self._visible_enabled(e)]
            # Codex's message editor is a ProseMirror control. Other visible
            # Edit controls (for example search) can appear in the same window.
            prose_mirror = [
                e for e in edits
                if "prosemirror" in (e.element_info.class_name or "").casefold()
            ]
            if len(prose_mirror) == 1:
                return prose_mirror[0]
            if len(prose_mirror) > 1:
                labels = self.composer_labels + ["使用 chatgpt work", "use chatgpt work"]
                named = [
                    e for e in prose_mirror
                    if any(label in e.element_info.name.casefold() for label in labels)
                ]
                if len(named) == 1:
                    return named[0]
                count = len(prose_mirror)
                error = f"找到 {count} 个 Codex 输入框"
            else:
                named = [
                    e for e in edits
                    if any(label in e.element_info.name.casefold() for label in self.composer_labels)
                ]
                candidates = named if named else edits
                if len(candidates) == 1:
                    return candidates[0]
                error = f"找到 {len(candidates)} 个候选输入框"
            if attempt < 2:
                time.sleep(0.2)
        raise RuntimeError(error)

    def handle_button(self, kind: str) -> str:
        try:
            with com_context():
                window = self._window()
                if kind == "approve":
                    choices = ("approve", "send")
                elif kind == "deny":
                    choices = ("deny", "stop")
                else:
                    return "未知按钮"
                for choice in choices:
                    button, name = self._find_button(window, self.labels[choice])
                    if button is not None:
                        # Avoid sending a click to a different foreground window.
                        self._window()
                        button.click_input()
                        return f"已点击 Codex 的 {name} 按钮"
                return "未找到匹配的 Codex 按钮；可用 inspect_codex_ui.py 查看名称"
        except ImportError:
            return "缺少 Windows 自动化依赖；先运行 setup_pc.ps1"
        except Exception as exc:
            return f"未执行：{exc}"

    def insert_text(self, text: str) -> str:
        if not text.strip():
            return "识别结果为空"
        try:
            import win32clipboard
            from pywinauto.keyboard import send_keys

            with com_context():
                window = self._voice_window()
                self._composer(window).click_input()
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                finally:
                    win32clipboard.CloseClipboard()
                send_keys("^v")
                time.sleep(0.1)
                return "已粘贴到 Codex 输入框；按第一个实体按钮发送"
        except ImportError:
            return "缺少 Windows 自动化依赖；文字已保存在电脑端面板"
        except Exception as exc:
            return f"未粘贴：{exc}；文字已保存在电脑端面板"

    def send_current_input(self) -> str:
        """Submit the current composer text without interrupting an active task."""
        try:
            from pywinauto.keyboard import send_keys

            with com_context():
                window = self._voice_window()
                button, name = self._find_button(window, self.labels["send"])
                if button is not None:
                    button.click_input()
                    return f"已点击 Codex 的 {name} 按钮"

                # While Codex is working the composer action commonly reads Stop,
                # so it must never be used as a substitute for Send. Submitting
                # from the focused composer keeps the follow-up as a queued or
                # steering message according to Codex's current conversation mode.
                composer = self._composer(window)
                composer.click_input()
                send_keys(self.send_shortcut)
                return "已从 Codex 输入框提交消息；未停止当前任务"
        except ImportError:
            return "缺少 Windows 自动化依赖"
        except Exception as exc:
            return f"未发送：{exc}"

    def clear_current_input(self) -> str:
        """Clear the visible Codex composer for an explicit voice command."""
        try:
            from pywinauto.keyboard import send_keys

            with com_context():
                window = self._voice_window()
                self._composer(window).click_input()
                send_keys("^a{BACKSPACE}")
                return "已清空 Codex 输入框"
        except ImportError:
            return "缺少 Windows 自动化依赖"
        except Exception as exc:
            return f"未清空：{exc}"
