# PATH 冲突导致 torch DLL 初始化失败 (WinError 1114)

## 现象

```
OSError: [WinError 1114] 动态链接库(DLL)初始化失败。
Error loading "torch\lib\c10.dll" or one of its dependencies.
```

同样的错误也出现在 `onnxruntime_pybind11_state.dll`（`onnxruntime`）、以及其他需要 VC++ 运行时的 native DLL。

## 排查过程

1. `c10.dll` 文件存在（1MB），不是文件缺失
2. 重装 torch（GPU + CPU 版）均无效
3. VC++ Redistributable x64 已安装（v14.28 + v14.44）
4. 尝试 `fastembed`（ONNX 运行时）同样 DLL 错误
5. 通过 `$env:Path` 只保留 Python 3.12 + 系统路径后 `import torch` 成功
6. 逐段对比发现 **Python 3.10 路径** `C:\Users\ethan1.zhao\AppData\Local\Programs\Python\Python310\` 在 PATH 中排在 Python 3.12 之前，导致 torch 的 DLL 加载器优先找到了 3.10 目录下的冲突 DLL

## 根因

Windows DLL 搜索顺序：PATH 目录从左到右。Python 3.10 的 `Library\bin\` 或 `DLLs\` 目录中包含与 torch 依赖的同名不同版本的 VC++ 运行时 DLL，导致 `c10.dll` 初始化时加载了错误的依赖版本。

## 修复

从 User PATH 中移除 Python 3.10 目录：

```powershell
$clean = [Environment]::GetEnvironmentVariable("Path","User") -replace 'Python310\\[^;]*;?',''
[Environment]::SetEnvironmentVariable("Path", $clean, "User")
```

`start_dev.ps1` 中也做了 PATH 清理，防止下次运行复现。

## 效果 ✅

| 组件 | 之前 | 之后 |
|------|------|------|
| `import torch` | ❌ WinError 1114 | ✅ OK |
| `HuggingFaceEmbedding(bge-small-zh-v1.5)` | ❌ 崩溃 | ✅ OK，维度 512 |
| 文件上传 → 向量索引 | MockEmbedding（随机） | BGE 中文模型（真实语义） |

## 备注

之前为绕过此问题做的延迟导入改造（`server/models/embedding.py`、`server/models/llm_api.py`、`server/splitters/compat.py`）仍然保留——它们在其他没有 torch 的环境中仍能提高启动健壮性，不需要回退。
