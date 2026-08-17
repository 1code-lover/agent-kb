# NorthAgent / ThinkRAG

NorthAgent 是一款本地优先的知识库助手。当前产品主线采用 **FastAPI + React + Electron + LlamaIndex**；仓库名、部分 Python 包名继续保留 `ThinkRAG`，用于兼容已有代码和数据。

## 当前能力

- 多知识库显式选择，未指定范围时默认拒绝问答，避免隐式跨库检索。
- 物理索引隔离：历史 `default` 知识库继续兼容 `storage/`，其他知识库分别持久化到 `storage/kbs/{kb_id}/`，各自拥有独立 docstore、index store 和 vector store 文件。
- 支持文件、Markdown、PDF、图片 OCR、网页导入，并提供导入回执和证据元数据。
- `/api/health` 提供 Embedding 诊断；本地 BGE 缓存缺失时，Knowledge Workspace 可点击“使用 ModelScope 准备缓存”，下载完成后自动重新预热。
- PaddleOCR 结果按几何坐标恢复阅读顺序；扫描 PDF 保留 `[Page N]` 页边界；规则表格可启发式恢复成 Markdown 表格；质量脚本覆盖关键词召回、行顺序和表格单元格召回。
- React Knowledge Workspace、Agent Workspace 与 Electron 桌面壳，桌面产品名为 **NorthAgent**。

## macOS 开发环境

必须优先使用已经验证通过的 conda 环境，不要使用仓库中由 Windows 创建的 `.venv`。

```bash
conda activate agent-kb
# 非交互脚本建议直接使用绝对路径
/opt/miniconda3/envs/agent-kb/bin/python --version
/opt/miniconda3/envs/agent-kb/bin/python -m pip install -r requirements.txt
```

项目基线为 Python 3.12，并锁定：

```text
llama_index==0.11.19
llama-index-core==0.11.19
```

## 本地启动

### 后端 API

```bash
/opt/miniconda3/envs/agent-kb/bin/python run_api.py
```

默认地址为 `http://127.0.0.1:18080`，健康诊断接口为 `/api/health`。

### Web 前端

```bash
cd webapp
npm install
npm run dev
```

### Electron 桌面端

```bash
cd desktop
npm install
NORTHAGENT_PYTHON=/opt/miniconda3/envs/agent-kb/bin/python npm run dev
```

## Embedding 缓存恢复

当 `/api/health` 返回“本地缓存不存在且运行时禁止远程下载”时，知识库页面会显示恢复按钮。按钮只允许使用白名单中的 `modelscope` 来源，不执行任意 shell 命令，也不要求用户输入密码或密钥。

也可使用 CLI：

```bash
/opt/miniconda3/envs/agent-kb/bin/python scripts/prepare_embedding_model_cache.py \
  --model bge-small-zh-v1.5 --download --provider modelscope
```

## 验证命令

```bash
# Python 非 slow 全量测试
/opt/miniconda3/envs/agent-kb/bin/python -m pytest tests/ -q -m "not slow"

# Web 单测与生产构建
node --test webapp/src/**/*.test.js
npm run build --prefix webapp

# Electron 测试
cd desktop
node --test src/*.test.js scripts/*.test.js
```

## 打包状态

当前可以进行未签名或 ad-hoc 的本地开发构建验证。正式 macOS 分发仍需要 Apple Developer 证书、签名、公证和安装后回归；这些外部发布门禁当前明确跳过，不能据此宣称正式 macOS 版本已经发布完成。

## 文档

- [项目进度与运行命令](./docs/project.md)
- [本地多知识库产品文档](./docs/20260722-local-multi-kb-assistant/)

## License

[MIT](./LICENSE)
