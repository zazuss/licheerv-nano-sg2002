"""Read-only accessibility-name diagnostic. Focus Codex before running."""

import pythoncom
from codex_desktop import CodexDesktop
from pywinauto import Desktop


def main():
    pythoncom.CoInitialize()
    try:
        config = {
            "button_labels": {"approve": [], "deny": [], "send": [], "stop": []},
            "composer_labels": [],
        }
        window = CodexDesktop(config)._window()
        print("前台 Codex 窗口中的可见按钮与输入框：")
        for control in window.descendants():
            if control.element_info.control_type in ("Button", "Edit") and control.is_visible():
                print(control.element_info.control_type, repr(control.window_text()))
    finally:
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
