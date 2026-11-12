"""ChatBI 算法问答链路（S1~S8）。

算法不直连数据库：runner / cache_store / resources 由调用方注入。
"""

from .run import ask
from .state import ChatState

__all__ = ["ask", "ChatState"]
