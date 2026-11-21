"""Go 制品发布的摘要、版本和草稿边界。"""

import json
import shutil
from pathlib import Path

import pytest

from scripts.release import go_native

COMMIT = "a" * 40
REPOSITORY = "hxse/vnpy-ctp"


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    folder = tmp_path_factory.mktemp("go-release")
    bundle = folder / "bundle"
    dist = folder / "dist"
    for name in go_native.MEMBERS:
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith(go_native.TRADER):
            source = go_native.ROOT / "vendor/ctp/linux-x86_64" / go_native.TRADER
            shutil.copyfile(source, target)
        elif name.endswith(go_native.MARKET):
            source = go_native.ROOT / "vendor/assessment/linux-x86_64" / go_native.MARKET
            shutil.copyfile(source, target)
        else:
            target.write_bytes(name.encode("ascii"))
    go_native.pack(dist, bundle, COMMIT, REPOSITORY)
    return dist


class Github:
    def __init__(self):
        self.value = None
        self.ref = None
        self.uploads = {}
        self.publish_count = 0
        self.create_count = 0
        self.reject_upload = False

    def release(self, tag):
        if self.value and not self.value["draft"] and self.value["tag_name"] == tag:
            return self.value

    def draft_release(self, tag):
        if self.value and self.value["draft"] and self.value["tag_name"] == tag:
            return self.value

    def tag_reference(self, tag):
        assert tag == go_native.label(COMMIT)
        return {"object": {"type": "commit", "sha": self.ref}} if self.ref is not None else None

    def create(self, tag, commit, *, body):
        assert body and body.startswith("Linux amd64")
        self.create_count += 1
        self.value = {"tag_name": tag, "target_commitish": commit, "draft": True, "id": 7}
        return self.value

    def assets(self, release_id):
        assert release_id == 7
        return [{"id": key, "name": key, "state": "uploaded", "digest": "sha256:" + go_native.sha(value)}
                for key, value in self.uploads.items()]

    def delete_asset(self, name):
        assert self.value["draft"]
        del self.uploads[name]

    def upload(self, release_id, path):
        assert self.value["draft"] and release_id == 7
        self.uploads[path.name] = path.read_bytes()
        if self.reject_upload:
            return {"digest": "sha256:" + "0" * 64}
        return {"digest": "sha256:" + go_native.sha(self.uploads[path.name])}

    def publish(self, release_id):
        assert release_id == 7 and self.value["draft"]
        self.value["draft"] = False
        self.ref = self.value["target_commitish"]
        self.publish_count += 1

    def manifest(self, tag):
        assert tag == self.value["tag_name"]
        return self.uploads["manifest.json"]


def test_go_release_can_resume_draft_and_reuse_published_assets(package):
    api = Github()
    api.reject_upload = True
    with pytest.raises(ValueError, match="上传后的 Go 制品摘要不匹配"):
        go_native.publish(package, COMMIT, REPOSITORY, api)
    assert api.value["draft"] and api.create_count == 1 and not api.publish_count
    api.reject_upload = False
    tag = go_native.publish(package, COMMIT, REPOSITORY, api)
    assert tag == go_native.label(COMMIT) and tag.startswith("go-v")
    assert api.create_count == api.publish_count == 1
    assert go_native.published_complete(api, COMMIT, REPOSITORY)
    assert go_native.publish(package, COMMIT, REPOSITORY, api) == tag
    assert api.publish_count == 1


def test_go_release_rejects_wrong_actual_tag_even_before_upload(package):
    api = Github()
    api.ref = "b" * 40
    with pytest.raises(ValueError, match="标签与完整 Git 提交不符"):
        go_native.publish(package, COMMIT, REPOSITORY, api)
    assert not api.create_count and not api.uploads


def test_go_release_binds_original_trader_and_market_libraries(package):
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["platform"] == "linux/amd64" and manifest["minimum_libc"] == "2.28"
    assert manifest["abi_version"] == 1
    assert Path(manifest["bundle"]["filename"]).name == go_native.BUNDLE
    manifest["files"][f"lib/{go_native.MARKET}"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="未使用原始厂商库"):
        go_native.validate_manifest(manifest, COMMIT, REPOSITORY)
