import sys
import os

def resource_path(relative_path):
    """ 获取资源的绝对路径，适用于 PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)