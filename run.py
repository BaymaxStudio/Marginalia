"""Marginalia 一键启动脚本"""
import os
import sys
import time
import threading
import webbrowser
import subprocess


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend", "dist")
ECDICT_PATH = os.path.join(BACKEND_DIR, "data", "ecdict.db")

# 根据操作系统确定 venv 中 Python 的路径
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(BACKEND_DIR, "venv", "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(BACKEND_DIR, "venv", "bin", "python")

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def check_ready():
    """检查必要组件是否就绪"""
    errors = []

    if not os.path.exists(VENV_PYTHON):
        errors.append("Python 虚拟环境未创建。请先运行: python3 setup.py")

    if not os.path.exists(ECDICT_PATH):
        errors.append("ECDICT 词典数据库未下载。请先运行: python3 setup.py")

    if not os.path.exists(FRONTEND_DIST):
        errors.append("前端未编译。请先运行: python3 setup.py")

    if errors:
        print("=" * 50)
        print("Marginalia 启动检查未通过：")
        for e in errors:
            print(f"  X {e}")
        print("=" * 50)
        sys.exit(1)


def open_browser_delayed():
    """等待服务启动后打开浏览器"""
    time.sleep(2)
    print(f"\n  浏览器已打开 {URL}")
    print("  按 Ctrl+C 停止服务\n")
    webbrowser.open(URL)


def main():
    check_ready()

    print("=" * 50)
    print("  Marginalia · AI 辅助学术阅读器")
    print("=" * 50)
    print(f"\n  启动中... 服务地址: {URL}\n")

    # 延迟打开浏览器
    threading.Thread(target=open_browser_delayed, daemon=True).start()

    # 使用 venv 中的 Python 启动 uvicorn
    os.chdir(BACKEND_DIR)
    subprocess.run([
        VENV_PYTHON, "-m", "uvicorn",
        "app.main:app",
        "--host", HOST,
        "--port", str(PORT),
    ])


if __name__ == "__main__":
    main()
