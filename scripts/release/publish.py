"""全矩阵校验后发布；已发布版本不可替换，失败只留下未公开草稿。"""

import argparse
import hashlib
import json
import os
from pathlib import Path

from packaging.utils import parse_wheel_filename

from scripts.release.catalog import PLATFORMS, PYTHONS, generate, platform_key
from scripts.release.github import Github
from scripts.release.version import commit_version


def verify_assets(assets: list[dict], files: dict[str, str]) -> None:
    if len(assets) != len(files) or {item["name"] for item in assets} != set(files):
        raise ValueError("Release 附件集合不完整或包含额外文件")
    for asset in assets:
        if asset.get("state") != "uploaded" or asset.get("digest") != "sha256:" + files[asset["name"]]:
            raise ValueError(f"Release 附件摘要不匹配：{asset['name']}")


def published_complete(api, commit: str, repository: str) -> bool:
    version = commit_version(commit)
    release = api.release("v" + version)
    if release is None or release["draft"]:
        return False
    if release["target_commitish"] != commit:
        raise ValueError("同名 Release 指向其他提交")
    body = api.manifest("v" + version)
    manifest = json.loads(body)
    if (manifest.get("commit"), manifest.get("version"), manifest.get("repository")) != (commit, version, repository):
        raise ValueError("已发布清单的身份不匹配")
    files = {}
    cells = set()
    for row in manifest["wheels"]:
        name, wheel_version, _, tags = parse_wheel_filename(row["filename"])
        if name != "vnpy-ctp" or str(wheel_version) != version:
            raise ValueError("已发布 wheel 的名称或版本不匹配")
        targets = {(tag.interpreter, platform_key(tag.platform)) for tag in tags}
        cell = (row["python"], row["platform"])
        if targets != {cell} or cell in cells or row["filename"] in files:
            raise ValueError("已发布矩阵存在重复或错配")
        cells.add(cell)
        files[row["filename"]] = row["sha256"]
    if cells != {(python, platform) for python in PYTHONS for platform in PLATFORMS}:
        raise ValueError("已发布矩阵不完整")
    checksums = "".join(f"{row['sha256']}  {row['filename']}\n" for row in manifest["wheels"]).encode()
    files["manifest.json"] = hashlib.sha256(body).hexdigest()
    files["SHA256SUMS"] = hashlib.sha256(checksums).hexdigest()
    verify_assets(api.assets(release["id"]), files)
    return True


def publish(directory: Path, commit: str, repository: str, github=None) -> str:
    manifest = generate(directory, commit, repository)
    tag = "v" + manifest["version"]
    paths = sorted(directory.glob("*.whl")) + [directory / "manifest.json", directory / "SHA256SUMS"]
    checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    api = github or Github(repository)
    release = api.release(tag)
    if release is not None:
        if release["target_commitish"] != commit:
            raise ValueError("已存在 Release 指向其他提交，拒绝覆盖")
        if not release["draft"]:
            verify_assets(api.assets(release["id"]), checksums)
            return tag
    else:
        release = api.create(tag, commit)
    # 草稿可以恢复；先完成本地全部校验，才清理草稿里的旧附件。
    for asset in api.assets(release["id"]):
        api.delete_asset(asset["id"])
    for path in paths:
        asset = api.upload(release["id"], path)
        if asset.get("digest") != "sha256:" + checksums[path.name]:
            raise ValueError(f"上传后的摘要不匹配：{path.name}")
    verify_assets(api.assets(release["id"]), checksums)
    api.publish(release["id"])
    return tag


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("commit")
    parser.add_argument("repository")
    parser.add_argument("--check-existing", action="store_true")
    args = parser.parse_args()
    if args.check_existing:
        published = published_complete(Github(args.repository), args.commit, args.repository)
        if output := os.environ.get("GITHUB_OUTPUT"):
            with Path(output).open("a") as stream:
                stream.write(f"published={str(published).lower()}\n")
        print("already published" if published else "build required")
    else:
        tag = publish(args.directory, args.commit, args.repository)
        print(f"https://github.com/{args.repository}/releases/tag/{tag}")


if __name__ == "__main__":
    main()
