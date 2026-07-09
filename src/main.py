"""Application entry point."""

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from src.config import AppConfig
from src.ui.main_window import MainWindow


def setup_logging(config: AppConfig) -> None:
    log_file = config.log_file
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main() -> None:
    config = AppConfig()
    setup_logging(config)

    app = QApplication(sys.argv)
    app.setApplicationName("录音转写")

    # Cyberpunk dark theme — only style containers, never custom-painted widgets
    app.setStyleSheet("""
        QMainWindow {
            background-color: #0a0c0d;
            color: #eee;
        }
        QStatusBar {
            background-color: #0d0f10;
            color: #666;
            border-top: 1px solid #1a1c1e;
        }
        QStatusBar::item {
            border: none;
        }
    """)

    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
