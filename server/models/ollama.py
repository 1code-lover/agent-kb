"""
模块功能：
- 提供 Ollama 服务健康检查、模型列表获取与 LLM 实例创建能力。

执行逻辑：
1. 通过 session_state 中的 ollama_api_url 进行连通性探测。
2. 可达时拉取模型列表并缓存到 session_state。
3. 按用户选择创建 Ollama LLM 并写入 Settings.llm。
"""

import requests
import streamlit as st
from ollama import Client
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama


def is_alive():
    """
    检查 Ollama 服务是否可访问。

    Returns:
        bool: HTTP 状态为 200 返回 True，否则返回 False。
    """
    try:
        response = requests.get(st.session_state.ollama_api_url)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        print("Failed to connect to Ollama")
        return False


def get_model_list():
    """
    获取 Ollama 服务端可用模型列表并更新会话缓存。

    Returns:
        list | None: 成功返回模型列表，失败返回 None。
    """
    st.session_state.ollama_models = []
    if is_alive():
        client = Client(host=st.session_state.ollama_api_url)
        response = client.list()
        models = response["models"]
        # 前端选择器只需要名称数组，单独缓存减少重复转换。
        for model in models:
            st.session_state.ollama_models.append(model["name"])
        return response["models"]
    else:
        print("Ollama is not alive")
        return None


def create_ollama_llm(model: str, temperature: float = 0.5, system_prompt: str = None) -> Ollama:
    """
    创建 Ollama LLM 实例并注册到 Settings.llm。

    Args:
        model: Ollama 模型名称。
        temperature: 采样温度。
        system_prompt: 可选系统提示词。

    Returns:
        Ollama | None: 创建成功返回模型实例，失败返回 None。
    """
    try:
        llm = Ollama(
            model=model,
            base_url=st.session_state.ollama_api_url,
            request_timeout=600,
            temperature=temperature,
            system_prompt=system_prompt,
        )
        print(f"created ollama model for query: {model}")
        Settings.llm = llm
        return llm
    except Exception as e:
        print(f"An error occurred while creating Ollama LLM: {e}")
        return None
