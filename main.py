from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.controller import AppController


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    controller = AppController(app)
    try:
        controller.initialize()
    except Exception as exc:
        controller.show_fatal_error("oh my word", f"Startup failed:\n{exc}")
        raise

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
