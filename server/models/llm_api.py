"""
模块功能：
- 封装 OpenAI 兼容 API 的 LLM 创建与可用性检测。

执行逻辑：
1. 根据用户配置创建 ChatOpenAI 并包装为 LangChainLLM。
2. 将可用实例写入 Settings.llm，供查询链路复用。
3. 在连通性检测中将常见错误分类，输出可读诊断信息。
"""

from llama_index.core import Settings
from langchain_openai import ChatOpenAI
from llama_index.llms.langchain import LangChainLLM


def _classify_openai_error(e: Exception) -> str:
    """
    对 OpenAI 兼容接口异常进行分类，便于上层生成可读诊断信息。

    Args:
        e: 捕获到的异常对象。

    Returns:
        str: 错误类别标识（forbidden_region/forbidden_403/invalid_key/other）。
    """
    msg = str(e)
    if "unsupported_country_region_territory" in msg:
        return "forbidden_region"
    if "Error code: 403" in msg or "403 Forbidden" in msg:
        return "forbidden_403"
    if "Error code: 401" in msg or "401 Unauthorized" in msg or "invalid_api_key" in msg:
        return "invalid_key"
    return "other"


def create_openai_llm(
    model_name: str,
    api_base: str,
    api_key: str,
    temperature: float = 0.5,
    system_prompt: str = None,
) -> ChatOpenAI:
    """
    创建 OpenAI 兼容 LLM 实例并注册到 Settings.llm。

    Args:
        model_name: 模型名称。
        api_base: OpenAI 兼容服务地址。
        api_key: API 密钥。
        temperature: 采样温度。
        system_prompt: 可选系统提示词。

    Returns:
        ChatOpenAI | None: 成功返回 LLM 包装实例，失败返回 None。
    """
    try:
        llm = LangChainLLM(
            llm=ChatOpenAI(
                openai_api_base=api_base,
                openai_api_key=api_key,
                model_name=model_name,
                temperature=temperature,
            ),
            system_prompt=system_prompt,
        )
        Settings.llm = llm
        return llm
    except Exception as e:
        print(f"An error occurred while creating the OpenAI compatibale model: {type(e).__name__}: {e}")
        return None


def check_openai_llm(model_name, api_base, api_key) -> bool:
    """
    检查 OpenAI 兼容模型配置是否可达且可用。

    Args:
        model_name: 目标模型名称。
        api_base: 服务地址。
        api_key: API 密钥。

    Returns:
        bool: 可连通并成功响应返回 True，否则返回 False。
    """
    # 通过一次最小调用验证模型可用性，避免保存不可用配置。
    try:
        llm = ChatOpenAI(
            openai_api_base=api_base,
            openai_api_key=api_key,
            model_name=model_name,
            timeout=5,
            max_retries=1
        )
        response = llm.invoke("Hello, World!")
        print(response)
        if response:
            return True
        else:
            return False
    except Exception as e:
        kind = _classify_openai_error(e)

        if kind in ("forbidden_region", "forbidden_403"):
            print(f"LLM API request forbidden (403). Region/policy may not be supported: {api_base}")
        elif kind == "invalid_key":
            print("Invalid API key (401).")
        else:
            print(f"Failed to verify LLM API: {e}")

        return False
