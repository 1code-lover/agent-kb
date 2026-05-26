"""
模块功能：
- 通过 r.jina.ai 代理抓取网页 Markdown 内容并转换为 Document。

执行逻辑：
1. 将原始 URL 前缀替换为 r.jina.ai 代理地址。
2. 从代理返回文本中提取 title、source 和 markdown 正文。
3. 组装为 LlamaIndex Document 列表返回。
"""

from typing import List, Optional, Dict, Callable
from datetime import datetime

import requests, re
from llama_index.core.readers.base import BasePydanticReader
from llama_index.core.schema import Document


class JinaWebReader(BasePydanticReader):
    """Jina web page reader.

    Reads pages from the web.

    """

    def __init__(self) -> None:
        """
        初始化 Jina Web Reader。
        """
        super().__init__()

    def load_data(self, urls: List[str]) -> List[Document]:
        """
        抓取 URL 列表并返回 Document 列表。

        Args:
            urls: 待抓取 URL 列表。

        Returns:
            List[Document]: 抓取并解析后的文档集合。

        Raises:
            ValueError: 输入不是 URL 列表时抛出。
        """
        if not isinstance(urls, list):
            raise ValueError("urls must be a list of strings.")

        documents = []
        for url in urls:
            new_url = "https://r.jina.ai/" + url
            response = requests.get(new_url)
            text = response.text

            # Extract Title
            title_match = re.search(r"Title:\s*(.*)", text)
            title = title_match.group(1) if title_match else None

            # Extract URL Source
            url_match = re.search(r"URL Source:\s*(.*)", text)
            url_source = url_match.group(1) if url_match else None

            # Extract Markdown Content
            markdown_match = re.search(r"Markdown Content:\s*(.*)", text, re.DOTALL)
            markdown_content = markdown_match.group(1).strip() if markdown_match else None

            # 元信息统一包含来源和抓取时间，便于后续追踪来源质量。
            metadata: Dict = {
                "title": title,
                "url_source": url_source,
                "creation_date": datetime.now().date().isoformat(),
            }

            documents.append(Document(text=markdown_content, id_=url, metadata=metadata or {}))

        return documents
