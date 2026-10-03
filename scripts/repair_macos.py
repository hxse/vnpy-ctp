"""完成路径修复后签名所有 Mach-O，再由 wheel 工具重建 RECORD。"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

MACH_O = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def binaries(root: Path) -> list[Path]:
    result = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            with path.open("rb") as stream:
                if stream.read(4) in MACH_O:
                    result.append(path)
    return result


def run(arguments: list[str]) -> None:
    subprocess.run(arguments, check=True, timeout=180)


def repair(wheel: Path, destination: Path, architectures: str) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("macOS wheel 修复必须在 macOS 执行")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ctp-macos-wheel-") as temporary:
        root = Path(temporary)
        repaired = root / "repaired"
        unpacked = root / "unpacked"
        run(["delocate-wheel", "--require-archs", architectures, "-w", str(repaired), str(wheel)])
        wheels = list(repaired.glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("依赖修复必须生成唯一 wheel")
        run([sys.executable, "-m", "wheel", "unpack", str(wheels[0]), "-d", str(unpacked)])
        distributions = list(unpacked.iterdir())
        if len(distributions) != 1 or not distributions[0].is_dir():
            raise ValueError("wheel 解包结果不唯一")
        native = binaries(distributions[0])
        if not native:
            raise ValueError("wheel 缺少 Mach-O 原生文件")
        for path in native:
            run(["codesign", "--force", "--sign", "-", "--timestamp=none", str(path)])
            run(["codesign", "--verify", "--strict", "--all-architectures", str(path)])
        # 签名改变二进制；由标准工具重建 RECORD，不能直接替换 ZIP 内文件。
        run([sys.executable, "-m", "wheel", "pack", str(distributions[0]), "-d", str(destination)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("architectures")
    args = parser.parse_args()
    repair(args.wheel, args.destination, args.architectures)
