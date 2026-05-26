"""本地 API 启动脚本。"""

from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("api.app:app", host="127.0.0.1", port=18080, reload=False)
