"""显式安装并验证一个本机构建的 wheel；不触发源码编译。"""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    path = args.wheel.resolve()
    if not path.is_file() or path.suffix != ".whl":
        parser.error("需要一个已构建的 wheel 文件")
    subprocess.run(["uv", "pip", "install", "--python", sys.executable,
                    "--no-deps", "--reinstall", str(path)], check=True)
    subprocess.run([sys.executable, "tests/native/check_wheel.py"], check=True)


if __name__ == "__main__":
    main()
