"""pytest 啟動時把 src/ 加入 import path，讓 engine / strategies / scraper 可直接 import。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
