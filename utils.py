import sys
import os

def resource_path(relative_path):
    """取得資源的絕對路徑，適用於開發環境和 PyInstaller 打包後的環境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
