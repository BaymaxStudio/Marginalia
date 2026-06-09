"""Marginalia 一键安装脚本

处理所有环境准备工作。用户只需要 Python >= 3.10，执行一次即可完成全部安装。
"""

import os
import sys
import venv
import shutil
import zipfile
import urllib.request
import subprocess


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
DATA_DIR = os.path.join(BACKEND_DIR, "data")

# ECDICT 下载地址（GitHub Releases）
ECDICT_URL = (
    "https://github.com/skywind3000/ECDICT/releases/download/"
    "1.0.28/ecdict-sqlite-28.zip"
)
# 备用 URL（国内镜像，如果主 URL 不可用可尝试）
ECDICT_MIRROR_URL = (
    "https://ghproxy.net/https://github.com/skywind3000/ECDICT/"
    "releases/download/1.0.28/ecdict-sqlite-28.zip"
)

# 根据操作系统确定 venv 中的可执行文件路径
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(BACKEND_DIR, "venv", "Scripts", "python.exe")
    VENV_PIP = os.path.join(BACKEND_DIR, "venv", "Scripts", "pip.exe")
else:
    VENV_PYTHON = os.path.join(BACKEND_DIR, "venv", "bin", "python")
    VENV_PIP = os.path.join(BACKEND_DIR, "venv", "bin", "pip")


def run_step(step_num: int, total: int, desc: str):
    """打印步骤标题"""
    print(f"\n[{step_num}/{total}] {desc}...")


def check_python():
    """步骤 1：检查 Python 版本"""
    run_step(1, 6, "检查 Python 版本")
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) < (3, 10):
        print(f"  X 需要 Python 3.10 或更高版本")
        print(f"    当前版本: Python {major}.{minor}")
        sys.exit(1)
    print(f"  OK Python {major}.{minor}")


def create_venv():
    """步骤 2：创建虚拟环境"""
    run_step(2, 6, "创建虚拟环境")
    venv_dir = os.path.join(BACKEND_DIR, "venv")
    if os.path.exists(venv_dir):
        print("  OK 虚拟环境已存在，跳过")
        return
    venv.create(venv_dir, with_pip=True)
    print("  OK 虚拟环境已创建")


def install_python_deps():
    """步骤 3：安装 Python 依赖"""
    run_step(3, 6, "安装 Python 依赖")
    requirements = os.path.join(BACKEND_DIR, "requirements.txt")
    subprocess.run(
        [VENV_PIP, "install", "-r", requirements, "--quiet"],
        check=True,
    )
    print("  OK Python 依赖安装完成")


def install_nltk_data():
    """步骤 4：下载 NLTK 词形还原数据"""
    run_step(4, 6, "下载 NLTK 数据")
    subprocess.run(
        [
            VENV_PYTHON, "-c",
            "import nltk; nltk.download('wordnet', quiet=True); "
            "nltk.download('omw-1.4', quiet=True)",
        ],
        check=True,
    )
    print("  OK NLTK 数据下载完成")


def _download_with_progress(url: str, dest: str, desc: str = ""):
    """下载文件并显示进度条"""

    # 创建一个自定义 opener 来处理重定向
    class RedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return urllib.request.Request(newurl)

    opener = urllib.request.build_opener(RedirectHandler)
    urllib.request.install_opener(opener)

    try:
        with urllib.request.urlopen(url) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 8192
            with open(dest, "wb") as f:
                while True:
                    block = response.read(block_size)
                    if not block:
                        break
                    f.write(block)
                    downloaded += len(block)
                    if total > 0:
                        pct = downloaded * 100 // total
                        mb_done = downloaded / 1024 / 1024
                        mb_total = total / 1024 / 1024
                        print(
                            f"\r    {desc}: {mb_done:.0f}/{mb_total:.0f}MB ({pct}%)",
                            end="", flush=True,
                        )
                if total > 0:
                    print()
    except Exception:
        # 清理不完整的下载文件
        if os.path.exists(dest):
            os.remove(dest)
        raise


def install_ecdict():
    """步骤 5：下载 ECDICT 词典数据库"""
    run_step(5, 6, "下载 ECDICT 词典")

    os.makedirs(DATA_DIR, exist_ok=True)
    ecdict_path = os.path.join(DATA_DIR, "ecdict.db")

    if os.path.exists(ecdict_path):
        size_mb = os.path.getsize(ecdict_path) / 1024 / 1024
        print(f"  OK ECDICT 词典已存在 ({size_mb:.0f}MB)，跳过")
        return

    print("  正在下载 ECDICT 词典（约 800MB，请耐心等待）...")

    zip_path = os.path.join(DATA_DIR, "ecdict.zip")

    # 尝试主 URL，失败后尝试镜像
    for attempt, url in enumerate([ECDICT_URL, ECDICT_MIRROR_URL], 1):
        try:
            if attempt > 1:
                print(f"  主 URL 不可用，尝试备用地址...")
            _download_with_progress(url, zip_path, "下载")
            break
        except Exception as e:
            if attempt == 2:
                print(f"\n  X 下载失败")
                print(f"    错误: {e}")
                print()
                print("  请手动下载 ECDICT 词典：")
                print(f"    1. 访问 https://github.com/skywind3000/ECDICT/releases")
                print(f"    2. 下载 ecdict-sqlite-28.zip")
                print(f"    3. 解压后将 stardict.db 放入 {ecdict_path}")
                print(f"    4. 重新运行 python setup.py")
                sys.exit(1)
            if os.path.exists(zip_path):
                os.remove(zip_path)

    # 解压 zip 并提取 stardict.db
    print("  正在解压...", end="", flush=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # ECDICT zip 包含 stardict.db
            if "stardict.db" in zf.namelist():
                zf.extract("stardict.db", DATA_DIR)
                os.rename(
                    os.path.join(DATA_DIR, "stardict.db"),
                    ecdict_path,
                )
            else:
                # 尝试找任何 .db 文件
                db_files = [n for n in zf.namelist() if n.endswith(".db")]
                if db_files:
                    zf.extract(db_files[0], DATA_DIR)
                    os.rename(
                        os.path.join(DATA_DIR, db_files[0]),
                        ecdict_path,
                    )
                else:
                    print(" X")
                    print(f"  X 无法在 zip 中找到词典数据库文件")
                    print(f"    zip 内容: {zf.namelist()[:10]}...")
                    sys.exit(1)
        os.remove(zip_path)
    except zipfile.BadZipFile:
        print(" X")
        print(f"  X 下载的文件损坏，请重新运行")
        if os.path.exists(zip_path):
            os.remove(zip_path)
        sys.exit(1)

    size_mb = os.path.getsize(ecdict_path) / 1024 / 1024
    print(f"  OK ECDICT 词典安装完成 ({size_mb:.0f}MB)")


def build_frontend():
    """步骤 6：编译前端"""
    run_step(6, 6, "编译前端")

    dist_dir = os.path.join(FRONTEND_DIR, "dist")

    if os.path.exists(dist_dir):
        print("  OK 前端已编译，跳过")
        return

    # 检查 Node.js 是否可用
    try:
        subprocess.run(
            ["node", "--version"], capture_output=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  X 前端未编译且未检测到 Node.js")
        print()
        print("  解决方案（二选一）：")
        print("  a) 安装 Node.js (https://nodejs.org) 后重新运行 setup")
        print("  b) 联系提供者获取已编译版本（frontend/dist/ 目录）")
        sys.exit(1)

    cwd = os.getcwd()
    try:
        os.chdir(FRONTEND_DIR)
        subprocess.run(["npm", "install"], check=True)
        subprocess.run(["npm", "run", "build"], check=True)
    finally:
        os.chdir(cwd)

    print("  OK 前端编译完成")


def main():
    print("=" * 50)
    print("  Marginalia · AI 辅助学术阅读器")
    print("  环境安装向导")
    print("=" * 50)

    check_python()
    create_venv()
    install_python_deps()
    install_nltk_data()
    install_ecdict()
    build_frontend()

    print()
    print("=" * 50)
    print("  OK Marginalia 安装完成！")
    print()
    print("  启动方式: python3 run.py")
    print()
    print("  首次使用请在设置页面配置 AI 服务：")
    print("  - 推荐 DeepSeek（国内用户）: https://platform.deepseek.com")
    print("  - 或 Claude: https://console.anthropic.com")
    print("  填入 API Key 后即可开始阅读。")
    print("=" * 50)


if __name__ == "__main__":
    main()
