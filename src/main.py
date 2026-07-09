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

    # Dark palette
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #111;
            color: #eee;
        }
        QTextEdit {
            border: 1px solid #333;
            border-radius: 4px;
            padding: 8px;
        }
        QStatusBar {
            background-color: #1a1a1a;
            color: #888;
        }
    """)

    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
