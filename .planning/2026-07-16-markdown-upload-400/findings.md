# Findings

## 已知事实
- 当前前端是 `127.0.0.1:5173`，API 指向 `127.0.0.1:18080`。
- `POST /api/kb` 成功，随后三次 `POST /api/kb/file/import` 均返回 400。
- registry 中 `kb_id=20260716`、`status=active`、`doc_count=0`。
- 中文 KB 名称存在乱码，暂未证明与上传 400 同源。
