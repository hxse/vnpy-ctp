"""显式验证完整评测变体；无账户、无前置、不开 GUI。"""

import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    from vnpy_ctp import CtpGateway
    from vnpy_ctp.api import MdApi, TdApi

    assert CtpGateway.default_name == "CTP"
    version = importlib.metadata.version("vnpy_ctp")
    assert version.endswith(".assessment"), version
    root = Path(__file__).resolve().parents[2]
    sdk = json.loads((root / "vendor/sdk.json").read_text(encoding="utf-8"))
    name = {"linux": "linux_x86_64", "win32": "windows_x86_64",
            "darwin": "macos_universal"}[sys.platform]
    expected = sdk["builds"][name]["api_version"]
    assert TdApi.getApiVersion() == expected
    assert MdApi.getApiVersion() == expected
    code = """
import tempfile
from vnpy_ctp.api import MdApi, TdApi
with tempfile.TemporaryDirectory() as path:
    for cls, create in [(TdApi, 'createFtdcTraderApi'), (MdApi, 'createFtdcMdApi')]:
        for production in (True, False):
            for init in (False, True):
                api = cls()
                api.exit()
                getattr(api, create)(path + '/', production)
                if init:
                    api.init()
                api.exit()
                api.release()
            api = cls()
            getattr(api, create)(path + '/', production)
            del api
print('assessment native lifecycle passed')
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "assessment native lifecycle passed" in result.stdout
    print("full assessment gateway and matching native APIs verified", flush=True)


if __name__ == "__main__":
    main()
