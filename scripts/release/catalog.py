"""核验整个 wheel 集合后生成长期发布清单，不靠文件数量冒充平台完整性。"""

import argparse
import hashlib
import json
import zipfile
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import quote

from packaging.tags import parse_tag
from packaging.utils import canonicalize_name, parse_wheel_filename

from scripts.release.version import commit_version

PYTHONS = ("cp310", "cp311", "cp312", "cp313", "cp314")
PLATFORMS = ("linux-x86_64", "windows-x86_64", "macos-x86_64", "macos-arm64")


def platform_key(tag: str) -> str:
    if tag.startswith("manylinux_") and tag.endswith("_x86_64"):
        return "linux-x86_64"
    if tag == "win_amd64":
        return "windows-x86_64"
    if tag.startswith("macosx_"):
        if tag.endswith("_x86_64"):
            return "macos-x86_64"
        if tag.endswith("_arm64"):
            return "macos-arm64"
    raise ValueError(f"非发布矩阵的平台标签：{tag}")


def inspect_wheel(path: Path, version: str) -> tuple[str, str]:
    name, parsed_version, _, tags = parse_wheel_filename(path.name)
    if canonicalize_name(name) != "vnpy-ctp" or str(parsed_version) != version:
        raise ValueError(f"wheel 包名或版本不匹配：{path.name}")
    cells = {(tag.interpreter, platform_key(tag.platform)) for tag in tags}
    if len(cells) != 1 or any(tag.abi != tag.interpreter for tag in tags):
        raise ValueError(f"wheel 必须对应一个普通 CPython 目标：{path.name}")
    cell = next(iter(cells))
    if cell[0] not in PYTHONS:
        raise ValueError(f"非发布矩阵的 Python：{cell[0]}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        wheel_paths = [name for name in names if name.endswith(".dist-info/WHEEL")]
        if len(metadata_paths) != 1 or len(wheel_paths) != 1:
            raise ValueError(f"wheel 元数据不唯一：{path.name}")
        metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
        wheel = BytesParser().parsebytes(archive.read(wheel_paths[0]))
        if metadata["Version"] != version or canonicalize_name(metadata["Name"]) != "vnpy-ctp":
            raise ValueError(f"wheel 内外版本不一致：{path.name}")
        if metadata.get_all("Requires-Dist", []):
            raise ValueError("独立交易扩展不得依赖 vnpy/GUI 或其他 Python 运行包")
        inner_tags = set().union(*(parse_tag(item) for item in wheel.get_all("Tag", [])))
        if inner_tags != tags or wheel["Root-Is-Purelib"] != "false":
            raise ValueError(f"wheel 标签或原生类型不一致：{path.name}")
        if any("vnctpmd" in item or "thostmduserapi" in item or "/gateway/" in item for item in names):
            raise ValueError("wheel 混入了行情扩展或完整网关")
        extensions = [name for name in names if name.startswith("vnpy_ctp/api/vnctptd.")
                      and name.endswith((".so", ".pyd"))]
        if len(extensions) != 1:
            raise ValueError(f"交易扩展缺失或不唯一：{path.name}")
        if not any("thosttraderapi" in name for name in names):
            raise ValueError(f"未随包提供原生交易库：{path.name}")
    return cell


def generate(directory: Path, commit: str, repository: str) -> dict:
    version = commit_version(commit)
    expected = {(python, platform) for python in PYTHONS for platform in PLATFORMS}
    seen: set[tuple[str, str]] = set()
    records = []
    for path in sorted(directory.glob("*.whl")):
        cell = inspect_wheel(path, version)
        if cell in seen:
            raise ValueError(f"重复目标：{cell}")
        seen.add(cell)
        records.append({
            "filename": path.name, "python": cell[0], "platform": cell[1],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
            "url": f"https://github.com/{repository}/releases/download/{quote('v' + version, safe='')}/{quote(path.name, safe='')}",
        })
    if seen != expected:
        raise ValueError(f"发布矩阵不完整；缺少 {sorted(expected-seen)}，额外 {sorted(seen-expected)}")
    root = Path(__file__).resolve().parents[2]
    capabilities = json.loads((root / "native/capabilities.json").read_text())
    result = {"version": version, "commit": commit, "repository": repository,
              "upstream_version": "6.7.11.4", "native_capabilities": capabilities,
              "wheels": records}
    (directory / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (directory / "SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['filename']}\n" for r in records))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("commit")
    parser.add_argument("repository")
    args = parser.parse_args()
    generate(args.directory, args.commit, args.repository)


if __name__ == "__main__":
    main()
