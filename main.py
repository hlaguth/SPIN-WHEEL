import sys
from PySide6.QtWidgets import QApplication
from config_window import ConfigWindow

def main():
    app = QApplication(sys.argv)
    config_window = ConfigWindow()
    config_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()