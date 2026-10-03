"""各平台共用交易扩展入口；库文件始终与对应 wheel 配套。"""

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    # 保留句柄，确保延迟加载时 DLL 搜索目录仍有效。
    _dll_directory = os.add_dll_directory(str(Path(__file__).resolve().parent))

from .vnctptd import TdApi  # noqa: E402

__all__ = ["TdApi"]
