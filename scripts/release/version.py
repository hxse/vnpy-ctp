"""每个提交对应唯一 PEP 440 版本；不以机器时间或运行次数命名。"""

import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_VERSION_LINE = r"^  version: '([^'\n]+)',$"
_match = re.search(_VERSION_LINE, (ROOT / "meson.build").read_text(encoding="utf-8"), re.M)
if _match is None:
    raise ValueError("meson.build 缺少唯一版本声明")
BASE_VERSION = re.sub(r"\.g(?:[0-9a-f]{40}|[0-9a-f]{64})$", "", _match[1])


def commit_version(commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
        raise ValueError("需要完整的小写 Git commit SHA")
    return f"{BASE_VERSION}.g{commit}"


def stamp(root: Path, commit: str) -> str:
    value = commit_version(commit)
    replacements = (("meson.build", _VERSION_LINE, f"  version: '{value}',"),)
    for name, pattern, replacement in replacements:
        path = root / name
        text, count = re.subn(pattern, replacement, path.read_text(encoding="utf-8"), flags=re.M)
        if count != 1:
            raise ValueError(f"{name} 必须且只能声明一个发行版本")
        path.write_text(text, encoding="utf-8")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("commit")
    parser.add_argument("--stamp", action="store_true")
    args = parser.parse_args()
    value = stamp(ROOT, args.commit) if args.stamp else commit_version(args.commit)
    print(value)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"version={value}\ntag=v{value}\n")


if __name__ == "__main__":
    main()
