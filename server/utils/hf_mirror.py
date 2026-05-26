"""
模块功能：
- 配置 HuggingFace 下载镜像地址环境变量。

执行逻辑：
1. 读取项目配置中的 HF_ENDPOINT。
2. 写入进程环境变量 HF_ENDPOINT。
3. 返回当前生效的镜像地址。
"""

def use_hf_mirror():
    """
    设置并返回 HuggingFace 镜像地址。

    Returns:
        str: 当前生效的 HF_ENDPOINT 地址。
    """
    import os
    from config import HF_ENDPOINT

    os.environ["HF_ENDPOINT"] = HF_ENDPOINT
    print(f"Use HF mirror: {os.environ['HF_ENDPOINT']}")
    return os.environ["HF_ENDPOINT"]
