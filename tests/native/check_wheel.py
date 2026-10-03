"""只验证已经安装的 wheel，不从源码重装；无账户、无外部行情或交易请求。"""

import importlib.metadata
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_child(arguments: list[str], *, timeout: int = 40) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


def check_installed_package() -> None:
    from vnpy_ctp import TdApi

    distribution = importlib.metadata.distribution("vnpy_ctp")
    assert not distribution.requires, distribution.requires
    files = [str(path) for path in distribution.files or ()]
    assert not any("vnctpmd" in path or "thostmduserapi" in path or "/gateway/" in path
                   for path in files)
    assert not any(name == "vnpy" or name.startswith("vnpy.") for name in sys.modules)
    assert isinstance(TdApi().getApiVersion(), str)
    limits = json.loads((ROOT / "native/capabilities.json").read_text())
    for name in limits["macos"]["unavailable_requests"]:
        python_name = name[0].lower() + name[1:]
        assert hasattr(TdApi, python_name) is (sys.platform != "darwin"), python_name
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as path:
            try:
                TdApi().createFtdcTraderApi(path + "/", False)
            except ValueError as error:
                assert "production-mode" in str(error)
            else:
                raise AssertionError("macOS 必须拒绝不支持的模式开关")
    print("native API", TdApi().getApiVersion(), "wheel", distribution.version, flush=True)


def check_no_front() -> None:
    code = """
import tempfile
from vnpy_ctp import TdApi
with tempfile.TemporaryDirectory() as path:
    for _ in range(10):
        api = TdApi()
        api.createFtdcTraderApi(path + '/', True)
        api.subscribePrivateTopic(2)
        api.subscribePublicTopic(2)
        api.init()
        assert api.reqQryOrder({}, 1) == -1
        assert api.reqQryTradingAccount({}, 2) == -1
        api.exit()
print('released')
"""
    assert "released" in run_child([sys.executable, "-c", code])


def check_common_header() -> None:
    with tempfile.TemporaryDirectory(prefix="ctp-native-probe-") as directory:
        build = Path(directory) / "build"
        setup = [sys.executable, "-m", "mesonbuild.mesonmain", "setup", str(build),
                 str(ROOT / "tests/native/probe"), f"-Dpython={sys.executable}"]
        if sys.platform == "win32":
            setup.append("--vsenv")
        run_child(setup, timeout=120)
        run_child([sys.executable, "-m", "mesonbuild.mesonmain", "compile", "-C", str(build)],
                  timeout=120)
        modules = [path for path in build.glob("_native_probe*")
                   if path.suffix in {".so", ".pyd"}]
        assert len(modules) == 1, modules
        # 在子进程释放 DLL 后再删除目录，避免 Windows 的已加载 DLL 文件锁。
        output = run_child([sys.executable, str(ROOT / "tests/native/probe/check.py"), str(modules[0])])
        assert "probe passed" in output


def main() -> None:
    check_installed_package()
    check_no_front()
    for scenario in ("callback_waiting_for_gil", "callback_in_progress"):
        output = run_child([sys.executable, str(ROOT / "tests/native/release_probe.py"), scenario])
        assert "released" in output
    check_common_header()
    print("all native wheel checks passed", flush=True)


if __name__ == "__main__":
    main()
