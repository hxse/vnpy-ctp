"""独立 Go C ABI 发布，按完整提交校验包、原库与附件。"""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import tarfile
from pathlib import Path
from urllib.parse import quote

from scripts.release.github import Github
from scripts.release.publish import verify_assets
from scripts.release.version import commit_version

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = "vnpy-ctp-go-native-linux-amd64.tar.gz"
TRADER = "libthosttraderapi_se.so"
MARKET = "libthostmduserapi_se.so"
MEMBERS = {
    "LICENSE", "NOTICE", "include/vnctp_go.h",
    "include/ctp/ThostFtdcUserApiStruct.h", "include/ctp/ThostFtdcUserApiDataType.h",
    "lib/libvnctp_go.so", f"lib/{TRADER}", f"lib/{MARKET}",
}
HEX = re.compile(r"[a-f0-9]{64}\Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def label(commit: str) -> str:
    return "go-v" + commit_version(commit)


def identity(commit: str, repository: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository):
        raise ValueError("仓库必须为 owner/name")
    sdk = json.loads((ROOT / "vendor/sdk.json").read_text(encoding="utf-8"))
    lock = {}
    for row in (ROOT / "vendor/sdk.sha256").read_text(encoding="utf-8").splitlines():
        checksum, path = row.split("  ", 1)
        lock[path] = checksum
    abi = re.search(r"^#define VNCTP_GO_ABI_VERSION ([1-9][0-9]*)$",
                    (ROOT / "native/go/vnctp_go.h").read_text(encoding="utf-8"), re.M)
    if abi is None:
        raise ValueError("缺少 Go 原生 ABI 版本")
    trader = sdk["builds"]["linux_x86_64"]
    return {
        "schema_version": 1,
        "repository": repository,
        "version": commit_version(commit),
        "commit": commit,
        "abi_version": int(abi[1]),
        "platform": "linux/amd64",
        "libc": "glibc",
        "minimum_libc": "2.28",
        "native_sdk": {
            "api_version": sdk["api_version"],
            "build": trader["api_version"],
            "libraries": {TRADER: trader["sha256"], MARKET: lock[f"vendor/assessment/linux-x86_64/{MARKET}"]},
        },
        "builder": {
            "image": (ROOT / "native/go/builder.lock").read_text(encoding="utf-8").strip(),
            "go": (ROOT / "native/go/.go-version").read_text(encoding="utf-8").strip(),
        },
    }


def record(data: bytes) -> dict:
    return {"size": len(data), "sha256": sha(data)}


def require_record(value: dict):
    if (set(value) != {"size", "sha256"} or type(value["size"]) is not int
            or value["size"] <= 0 or not isinstance(value["sha256"], str) or not HEX.fullmatch(value["sha256"])):
        raise ValueError("Go 制品文件摘要或长度无效")


def bundle_url(commit: str, repository: str) -> str:
    return f"https://github.com/{repository}/releases/download/{quote(label(commit), safe='')}/{BUNDLE}"


def validate_manifest(value: dict, commit: str, repository: str) -> None:
    required = identity(commit, repository)
    if set(value) != set(required) | {"bundle", "files"} or any(value[k] != v for k, v in required.items()):
        raise ValueError("Go 制品清单身份不匹配")
    bundle = dict(value["bundle"])
    if bundle.pop("filename", None) != BUNDLE or bundle.pop("url", None) != bundle_url(commit, repository):
        raise ValueError("Go 制品归档 URL 或文件名不符")
    require_record(bundle)
    if set(value["files"]) != MEMBERS:
        raise ValueError("Go 制品归档文件集合不符")
    for entry in value["files"].values():
        require_record(entry)
    for library, checksum in required["native_sdk"]["libraries"].items():
        if value["files"][f"lib/{library}"]["sha256"] != checksum:
            raise ValueError("Go 制品未使用原始厂商库")


def checksum_file(value: dict) -> bytes:
    return f"{value['bundle']['sha256']}  {BUNDLE}\n".encode("ascii")


def pack(directory: Path, source: Path, commit: str, repository: str) -> None:
    value = identity(commit, repository)
    files = {name: (source / name).read_bytes() for name in sorted(MEMBERS)}
    value["files"] = {name: record(body) for name, body in files.items()}
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / BUNDLE
    with archive.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as tar:
                for name, body in files.items():
                    item = tarfile.TarInfo(name)
                    item.size = len(body)
                    item.mode = 0o644
                    tar.addfile(item, io.BytesIO(body))
    value["bundle"] = record(archive.read_bytes()) | {"filename": BUNDLE, "url": bundle_url(commit, repository)}
    validate_manifest(value, commit, repository)
    (directory / "manifest.json").write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (directory / "SHA256SUMS").write_bytes(checksum_file(value))


def expected_assets(manifest_body: bytes, commit: str, repository: str) -> dict:
    value = json.loads(manifest_body)
    validate_manifest(value, commit, repository)
    return {BUNDLE: value["bundle"]["sha256"], "manifest.json": sha(manifest_body),
            "SHA256SUMS": sha(checksum_file(value))}


def inspect_package(directory: Path, commit: str, repository: str) -> dict:
    raw = (directory / "manifest.json").read_bytes()
    checksums = expected_assets(raw, commit, repository)
    if any(sha((directory / name).read_bytes()) != checksum for name, checksum in checksums.items()):
        raise ValueError("Go 制品附件摘要不匹配")
    value = json.loads(raw)
    archive = directory / BUNDLE
    if archive.stat().st_size != value["bundle"]["size"]:
        raise ValueError("Go 制品归档长度不匹配")
    with tarfile.open(archive, mode="r:gz") as packed:
        members = packed.getmembers()
        if len(members) != len(MEMBERS) or {item.name for item in members} != MEMBERS:
            raise ValueError("Go 制品归档文件集合不符")
        for member in members:
            if not member.isfile() or member.size != value["files"][member.name]["size"]:
                raise ValueError("Go 制品归档成员类型或长度无效")
            content = packed.extractfile(member)
            if content is None or record(content.read()) != value["files"][member.name]:
                raise ValueError("Go 制品归档成员摘要不匹配")
    return checksums


def verify_tag(api, tag: str, commit: str, *, require=False) -> None:
    ref = api.tag_reference(tag)
    if ref is None and not require:
        return
    if ref is None or ref.get("object", {}).get("type") != "commit" or ref["object"]["sha"] != commit:
        raise ValueError("Go Release 标签与完整 Git 提交不符")


def published_complete(api, commit: str, repository: str) -> bool:
    tag = label(commit)
    release = api.release(tag)
    if release is None or release["draft"]:
        verify_tag(api, tag, commit)
        return False
    verify_tag(api, tag, commit, require=True)
    if release["target_commitish"] != commit:
        raise ValueError("Go Release 指向其他提交")
    checksums = expected_assets(api.manifest(tag), commit, repository)
    verify_assets(api.assets(release["id"]), checksums)
    return True


def publish(directory: Path, commit: str, repository: str, github=None) -> str:
    checksums = inspect_package(directory, commit, repository)
    api = github or Github(repository)
    tag = label(commit)
    verify_tag(api, tag, commit)
    release = api.release(tag)
    if release is None:
        release = api.draft_release(tag)
    if release is not None and release["target_commitish"] != commit:
        raise ValueError("Go Release 指向其他提交")
    if release is not None and not release["draft"]:
        verify_tag(api, tag, commit, require=True)
        verify_assets(api.assets(release["id"]), checksums)
        return tag
    if release is None:
        release = api.create(tag, commit, body="Linux amd64/glibc 的 CTP 原生 C ABI 制品。链接信息与摘要见 manifest.json。")
    for asset in api.assets(release["id"]):
        api.delete_asset(asset["id"])
    for name, checksum in checksums.items():
        asset = api.upload(release["id"], directory / name)
        if asset.get("digest") != "sha256:" + checksum:
            raise ValueError(f"上传后的 Go 制品摘要不匹配：{name}")
    verify_assets(api.assets(release["id"]), checksums)
    verify_tag(api, tag, commit)
    api.publish(release["id"])
    verify_tag(api, tag, commit, require=True)
    return tag


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("directory", type=Path)
    cli.add_argument("commit")
    cli.add_argument("repository")
    operation = cli.add_mutually_exclusive_group()
    operation.add_argument("--check-existing", action="store_true")
    operation.add_argument("--pack", type=Path)
    args = cli.parse_args()
    if args.pack is not None:
        pack(args.directory, args.pack, args.commit, args.repository)
        inspect_package(args.directory, args.commit, args.repository)
    elif args.check_existing:
        published = published_complete(Github(args.repository), args.commit, args.repository)
        if output := os.environ.get("GITHUB_OUTPUT"):
            with Path(output).open("a", encoding="utf-8") as stream:
                stream.write(f"published={str(published).lower()}\n")
        print("already published" if published else "build required")
    else:
        tag = publish(args.directory, args.commit, args.repository)
        print(f"https://github.com/{args.repository}/releases/tag/{tag}")


if __name__ == "__main__":
    main()
