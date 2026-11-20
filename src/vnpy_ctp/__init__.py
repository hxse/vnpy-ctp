"""导出 CTP 的轻量原生 API。"""

import sys
from importlib.metadata import version

from .api import TdApi

__version__ = version("vnpy_ctp")
__all__ = ["TdApi", "__version__"]
if sys.platform == "linux":
    __all__.append("MdApi")


def __getattr__(name):
    if name == "MdApi" and sys.platform == "linux":
        from .api.vnctpmd import MdApi

        return MdApi
    raise AttributeError(name)
