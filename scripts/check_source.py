"""离线检查原生二进制来源和必须保留的补丁边界。"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root: Path = ROOT) -> None:
    # 厂商输入保持 sdk.sha256 所列原始字节；wheel 修复后的摘要另行计算。
    for line in (root / "vendor/sdk.sha256").read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        if name.startswith(("vendor/ctp/", "vendor/assessment/")):
            actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"原生库校验失败：{name}")
    cpp = (root / "native/vnctptd.cpp").read_text(encoding="utf-8")
    header = (root / "native/vnctp.h").read_text(encoding="utf-8")
    td_header = (root / "native/vnctptd.h").read_text(encoding="utf-8")
    assert 'call_guard<gil_scoped_release>()' in cpp
    assert "atomic<bool> active{false}" in td_header
    assert "shared_ptr<void> task_data" in header and "shared_ptr<void> task_error" in header
    assert "discarded.swap(queue_)" in header and "PyUnicode_Decode" in header
    assert "iconv_open" not in header
    limits = json.loads((root / "native/capabilities.json").read_text(encoding="utf-8"))
    assert limits["macos"]["unavailable_requests"] == []
    assert limits["macos"]["production_mode_switch"] is True
    sdk = json.loads((root / "vendor/sdk.json").read_text(encoding="utf-8"))
    for build in sdk["builds"].values():
        assert build["api_version"].startswith("v" + sdk["api_version"] + "_")
        assert any(line.startswith(build["sha256"] + "  ") for line in
                   (root / "vendor/sdk.sha256").read_text().splitlines())
    assert "__APPLE__" not in cpp and "__APPLE__" not in td_header
    print("native library checksums and required patches verified")


if __name__ == "__main__":
    check()
