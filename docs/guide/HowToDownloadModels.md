# ThinkRAG / NorthAgent 模型下载与本地缓存说明

> 当前 source of truth：本文是 embedding 模型下载、导入和本地缓存准备的唯一 canonical 说明；`docs/HowToDownloadModels.md` 仅保留为根目录兼容跳转页。

## 1. 当前默认约定

- 默认 embedding 模型：`bge-small-zh-v1.5`
- 默认模型根目录：仓库根目录下的 `localmodels/`
- 默认本地缓存目标：`localmodels/BAAI/bge-small-zh-v1.5`
- 如果桌面运行时设置了 `KB_MODEL_ROOT` / `NORTHAGENT_MODEL_ROOT` / `THINKRAG_MODEL_ROOT` / `FOXGLOVE_MODEL_ROOT`，模型根目录会跟随该运行时路径覆盖

当前项目主线已经不是“手工 cd 到某个目录后直接下载模型”这一个路径。**推荐优先使用脚本化缓存准备流程**，这样能把诊断、下载和离线导入统一到同一套契约下。

## 2. 推荐方式：使用缓存准备脚本

先做诊断，不实际下载：

```powershell
python -m scripts.prepare_embedding_model_cache
```

如果要实际下载默认 embedding 模型：

```powershell
python -m scripts.prepare_embedding_model_cache --download
```

如果网络环境更适合 ModelScope：

```powershell
python -m scripts.prepare_embedding_model_cache --download --provider modelscope
```

如果你已经从其他机器、离线包或共享目录拿到了模型文件，也可以直接导入：

```powershell
python -m scripts.prepare_embedding_model_cache --source-dir D:\model-cache\bge-small-zh-v1.5
```

脚本能力边界：

1. 未传 `--download` 时，只输出当前 embedding 缓存诊断；
2. 传 `--download` 时，才会把模型下载到当前 `localmodels/` 契约路径；
3. 传 `--source-dir` 时，会把已有本地模型目录复制到项目缓存目录，适合离线导入；
4. `--provider` 当前支持 `huggingface` 和 `modelscope`。

## 3. 手工下载回退方案

如果你不想走脚本，或需要手工验证 HuggingFace 下载链路，也可以直接执行：

### 3.1 安装或升级 huggingface_hub

```powershell
python -m pip install -U huggingface_hub
```

### 3.2 如需镜像，配置 HF endpoint

```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
```

### 3.3 下载默认 embedding 模型到当前契约路径

```powershell
huggingface-cli download --resume-download BAAI/bge-small-zh-v1.5 --local-dir localmodels/BAAI/bge-small-zh-v1.5
```

### 3.4 如需默认 reranker，也可额外下载

```powershell
huggingface-cli download --resume-download BAAI/bge-reranker-base --local-dir localmodels/BAAI/bge-reranker-base
```

## 4. 什么时候该优先脚本，而不是手工命令

优先用 `scripts.prepare_embedding_model_cache` 的场景：

- 你想先确认当前模型是否已经存在本地缓存；
- 你想把“诊断 / 下载 / 离线导入”收口到同一条运维口径；
- 你希望沿用项目当前 `localmodels/` 与运行时 override 契约，而不是自己拼路径；
- 你需要在 HuggingFace 与 ModelScope 间切换 provider。

手工命令更适合的场景：

- 你要单独验证 `huggingface-cli download` 是否通；
- 你在排查镜像 / 代理问题；
- 你只想下载某个额外模型，不想走项目脚本。

## 5. 常见问题

### 5.1 为什么不再推荐 `mkdir ~/ThinkRAG/localmodels && cd ...` 这种固定路径写法？

因为当前项目已经支持运行时 `KB_MODEL_ROOT` 覆盖，也有桌面打包与开发模式两种路径来源。继续把根目录文档写成单一绝对路径，会误导协作者以为 `~/ThinkRAG/localmodels` 是唯一有效口径。

### 5.2 如果 API 冷启动很慢，和模型缓存有关吗？

有关系。embedding 模型不存在本地缓存时，预热与首次加载通常会更慢。优先检查 `python -m scripts.prepare_embedding_model_cache` 的诊断输出，再决定是否下载或导入缓存。

### 5.3 需要把 `localmodels/` 提交到仓库吗？

通常不需要。模型文件体积大，而且项目默认把这类运行时缓存视为本地资产；如需交付，请按打包 / 发布流程或离线包流程处理。
