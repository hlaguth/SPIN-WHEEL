import sys
import os

def resource_path(relative_path):
    """取得資源的絕對路徑，適用於開發環境和 PyInstaller 打包後的環境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def external_path(relative_path):
    """取得外部資源的絕對路徑 (放在 EXE 同層級)"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
