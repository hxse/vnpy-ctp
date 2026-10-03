import zipfile
from pathlib import Path

import pytest
from packaging.tags import parse_tag

from scripts.release.catalog import generate, inspect_wheel
from scripts.release.version import BASE_VERSION, commit_version, stamp

COMMIT = "a" * 40
VERSION = commit_version(COMMIT)
PLATFORMS = ["manylinux_2_28_x86_64", "win_amd64", "macosx_11_0_x86_64", "macosx_11_0_arm64"]


def wheel(directory: Path, python="cp313", platform="manylinux_2_28_x86_64", *, dependency=None):
    name = f"vnpy_ctp-{VERSION}-{python}-{python}-{platform}.whl"
    path = directory / name
    metadata = f"Metadata-Version: 2.4\nName: vnpy_ctp\nVersion: {VERSION}\n"
    if dependency:
        metadata += f"Requires-Dist: {dependency}\n"
    tags = parse_tag(f"{python}-{python}-{platform}")
    wheel_info = "Wheel-Version: 1.0\nRoot-Is-Purelib: false\n" + "".join(f"Tag: {tag}\n" for tag in tags)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"vnpy_ctp-{VERSION}.dist-info/METADATA", metadata)
        archive.writestr(f"vnpy_ctp-{VERSION}.dist-info/WHEEL", wheel_info)
        archive.writestr(f"vnpy_ctp/api/vnctptd.{python}." + ("pyd" if platform.startswith("win") else "so"), b"fixture")
        archive.writestr("vnpy_ctp/api/libthosttraderapi_se.so", b"fixture")
    return path


@pytest.mark.parametrize("commit", ["", "main", "a" * 12, "A" * 40, "x" * 40, "a" * 40 + "\n"])
def test_version_rejects_refs_and_incomplete_commits(commit):
    with pytest.raises(ValueError, match="完整"):
        commit_version(commit)


def test_version_is_unique_deterministic_and_stamps_meson_metadata(tmp_path):
    (tmp_path / "meson.build").write_text(f"  version: '{BASE_VERSION}',\n")
    assert stamp(tmp_path, COMMIT) == VERSION
    assert stamp(tmp_path, COMMIT) == VERSION
    assert commit_version("b" * 40) != VERSION
    assert VERSION in (tmp_path / "meson.build").read_text()


def test_complete_matrix_produces_fixed_urls_and_checksums(tmp_path):
    for python in ("cp310", "cp311", "cp312", "cp313", "cp314"):
        for platform in PLATFORMS:
            wheel(tmp_path, python, platform)
    result = generate(tmp_path, COMMIT, "hxse/vnpy-ctp")
    assert len(result["wheels"]) == 20
    assert len((tmp_path / "SHA256SUMS").read_text().splitlines()) == 20
    assert all("/releases/download/v" in row["url"] and len(row["sha256"]) == 64
               for row in result["wheels"])


def test_missing_platform_prevents_publication_catalog(tmp_path):
    wheel(tmp_path)
    with pytest.raises(ValueError, match="矩阵不完整"):
        generate(tmp_path, COMMIT, "hxse/vnpy-ctp")
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize("platform", ["linux_x86_64", "manylinux_2_28_aarch64", "musllinux_1_2_x86_64", "win32"])
def test_unsupported_platform_is_not_advertised(tmp_path, platform):
    with pytest.raises(ValueError, match="平台标签"):
        inspect_wheel(wheel(tmp_path, platform=platform), VERSION)


def test_wheel_cannot_silently_install_vnpy_framework(tmp_path):
    with pytest.raises(ValueError, match="不得依赖"):
        inspect_wheel(wheel(tmp_path, dependency="vnpy>=3.0.0"), VERSION)


def test_archive_metadata_must_agree_with_filename(tmp_path):
    path = wheel(tmp_path)
    with pytest.raises(ValueError, match="包名或版本"):
        inspect_wheel(path, commit_version("b" * 40))
