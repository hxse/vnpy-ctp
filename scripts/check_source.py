"""离线检查原生二进制来源和必须保留的补丁边界。"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path = ROOT) -> None:
    # 二进制保持迁移基线原样；C++ 的可审阅平台适配由源码和补丁记录维护。
    for line in (root / "vendor/migration.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if name.startswith("vendor/ctp/"):
            actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"原生库校验失败：{name}")
    cpp = (root / "native/vnctptd.cpp").read_text()
    header = (root / "native/vnctp.h").read_text()
    td_header = (root / "native/vnctptd.h").read_text()
    assert 'call_guard<gil_scoped_release>()' in cpp
    assert "atomic<bool> active{false}" in td_header
    assert "shared_ptr<void> task_data" in header and "shared_ptr<void> task_error" in header
    assert "discarded.swap(queue_)" in header and "PyUnicode_Decode" in header
    assert "iconv_open" not in header
    limits = json.loads((root / "native/capabilities.json").read_text())
    assert len(limits["macos"]["unavailable_requests"]) == 8
    print("native library checksums and required patches verified")


if __name__ == "__main__":
    check()
