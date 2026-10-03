import hashlib
from copy import deepcopy

import pytest

from scripts.release.publish import publish, published_complete
from tests.unit.test_release import COMMIT, PLATFORMS, VERSION, wheel


class Github:
    def __init__(self):
        self.value = None
        self.files = []
        self.events = []
        self.fail_upload = False
        self.manifest_bytes = None

    def release(self, tag):
        self.events.append("read")
        return deepcopy(self.value)

    def assets(self, release_id):
        return deepcopy(self.files)

    def create(self, tag, commit):
        self.events.append("create-draft")
        self.value = {"id": 1, "target_commitish": commit, "draft": True}
        return deepcopy(self.value)

    def delete_asset(self, asset_id):
        self.events.append("delete-draft-asset")
        self.files = [item for item in self.files if item["id"] != asset_id]

    def upload(self, release_id, path):
        self.events.append("upload")
        if self.fail_upload:
            raise RuntimeError("simulated upload failure")
        item = {"id": len(self.files) + 1, "name": path.name, "state": "uploaded",
                "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}
        self.files.append(item)
        if path.name == "manifest.json":
            self.manifest_bytes = path.read_bytes()
        return item

    def manifest(self, tag):
        return self.manifest_bytes

    def publish(self, release_id):
        self.events.append("publish")
        self.value["draft"] = False


@pytest.fixture
def matrix(tmp_path):
    for python in ("cp310", "cp311", "cp312", "cp313", "cp314"):
        for platform in PLATFORMS:
            wheel(tmp_path, python, platform)
    return tmp_path


def test_publish_only_after_all_assets_uploaded_and_verified(matrix):
    api = Github()
    assert publish(matrix, COMMIT, "hxse/vnpy-ctp", api) == "v" + VERSION
    assert api.events[1] == "create-draft" and api.events[-1] == "publish"
    assert len(api.files) == 22 and not api.value["draft"]


def test_upload_failure_keeps_draft_and_can_resume(matrix):
    api = Github()
    api.fail_upload = True
    with pytest.raises(RuntimeError, match="upload failure"):
        publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    assert api.value["draft"] and "publish" not in api.events
    api.fail_upload = False
    publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    assert not api.value["draft"]


def test_published_release_is_reused_without_mutation(matrix):
    api = Github()
    publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    api.events.clear()
    publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    assert api.events == ["read"]
    assert published_complete(api, COMMIT, "hxse/vnpy-ctp")


def test_published_missing_artifact_cannot_skip_revalidation(matrix):
    api = Github()
    publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    api.files.pop()
    with pytest.raises(ValueError, match="附件集合"):
        published_complete(api, COMMIT, "hxse/vnpy-ctp")


def test_published_mismatched_asset_is_not_overwritten(matrix):
    api = Github()
    publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    api.files[0]["digest"] = "sha256:" + "0" * 64
    api.events.clear()
    with pytest.raises(ValueError, match="摘要不匹配"):
        publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    assert api.events == ["read"]


def test_other_commit_and_incomplete_matrix_cannot_publish(matrix, tmp_path):
    api = Github()
    api.value = {"id": 1, "target_commitish": "b" * 40, "draft": True}
    with pytest.raises(ValueError, match="其他提交"):
        publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    assert api.events == ["read"]
    next(matrix.glob("*.whl")).unlink()
    api.events.clear()
    with pytest.raises(ValueError, match="矩阵不完整"):
        publish(matrix, COMMIT, "hxse/vnpy-ctp", api)
    assert not api.events
