import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.release.version import BASE_VERSION
from scripts.repair_macos import binaries


def test_version_stamping_works_with_ascii_locale_and_chinese_comments(tmp_path):
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / "scripts/release/version.py"
    target.parent.mkdir(parents=True)
    shutil.copyfile(root / "scripts/release/version.py", target)
    (tmp_path / "meson.build").write_text(
        f"  version: '{BASE_VERSION}',\n# 必须保留的中文注释\n", encoding="utf-8",
    )
    env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
    env.pop("GITHUB_OUTPUT", None)
    result = subprocess.run([sys.executable, "-X", "utf8=0", str(target), "a" * 40, "--stamp"],
                            env=env, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    contents = (tmp_path / "meson.build").read_text(encoding="utf-8")
    assert "中文注释" in contents and ".g" + "a" * 40 in contents


def test_macho_detection_includes_versioned_framework_and_extension(tmp_path):
    framework = tmp_path / "api/ctp.framework/Versions/A/ctp"
    framework.parent.mkdir(parents=True)
    framework.write_bytes(b"\xca\xfe\xba\xbe" + b"fixture")
    extension = tmp_path / "api/vnctptd.so"
    extension.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
    (tmp_path / "api/header.h").write_text("// text", encoding="utf-8")
    (tmp_path / "api/linux.so").write_bytes(b"\x7fELF")
    assert set(binaries(tmp_path)) == {framework, extension}
