"""对子进程编译探针验证真实公共头文件行为。"""

import importlib.util
import sys

spec = importlib.util.spec_from_file_location("_native_probe", sys.argv[1])
assert spec is not None and spec.loader is not None
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
assert probe.decode("正常：报单已接受".encode("gb18030")) == "正常：报单已接受"
assert probe.decode(b"bad\xff") == "bad\ufffd"
assert probe.decode(b"") == ""
assert probe.queue_lifetime() == {
    "queued": 1, "discarded": 0, "remaining": 0, "terminated": True,
}
print("probe passed")
