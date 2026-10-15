"""固定 ABI 缓存中的单任务增量构建；构建依赖由 just setup 准备。"""

import subprocess
import sys
import sysconfig


def main() -> None:
    target = sys.implementation.cache_tag + "-" + sysconfig.get_platform()
    subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation",
                    "--outdir", ".wheelhouse", f"-Cbuild-dir=build/{target}",
                    "-Ccompile-args=-j1"], check=True)


if __name__ == "__main__":
    main()
