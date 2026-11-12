"""ChatBI 后端服务。

启动时把项目根目录加入 sys.path，使顶层 `algorithm` 包可被导入。
算法不直连库，后端通过注入 QueryRunner / CacheStore / ResourceProvider 调用。
"""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
