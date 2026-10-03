"""仅提供修复后的 CTP 交易 API；不依赖 VeighNa 网关或 GUI。"""

from importlib.metadata import version

from .api import TdApi

__version__ = version("vnpy_ctp")
__all__ = ["TdApi", "__version__"]
