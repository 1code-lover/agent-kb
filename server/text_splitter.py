"""
模块功能：
- 根据运行环境创建文本切分器，并注册到 LlamaIndex Settings。

执行逻辑：
1. 开发模式使用 SentenceSplitter。
2. 生产模式使用基于 Spacy 的切分器并通过 LangchainNodeParser 适配。
3. 模块加载时将默认切分器写入 Settings.text_splitter。
"""

from config import DEV_MODE
from llama_index.core import Settings


def create_text_splitter(chunk_size=2048, chunk_overlap=512):
    """
    功能：
    - 创建适配当前环境的文本切分器。

    输入：
    - chunk_size(int): 每个文本块的目标长度。
    - chunk_overlap(int): 相邻文本块的重叠长度。

    执行逻辑：
    1. DEV_MODE=True 时返回 SentenceSplitter。
    2. DEV_MODE=False 时返回 SpacyTextSplitter 的 LlamaIndex 适配器。

    输出：
    - 文本切分器对象（可被 Settings.text_splitter 使用）。
    """
    if DEV_MODE:
        # 开发环境优先使用轻量、依赖少的默认切分器。
        from llama_index.core.node_parser import SentenceSplitter

        sentence_splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        return sentence_splitter
    
    else:
        # 生产环境使用 Spacy，中文分句效果更稳定，便于后续检索与召回。
        # 依赖参考：
        # - pip install spacy
        # - python -m spacy download zh_core_web_sm
        from langchain.text_splitter import SpacyTextSplitter
        from llama_index.core.node_parser import LangchainNodeParser

        spacy_text_splitter = LangchainNodeParser(SpacyTextSplitter(
            pipeline="zh_core_web_sm",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ))

        return spacy_text_splitter


Settings.text_splitter = create_text_splitter()