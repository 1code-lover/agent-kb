"""
模块功能：
- 基于 BeautifulSoup 抓取网页并转换为 LlamaIndex Document。

执行逻辑：
1. 对指定 hostname 走定制提取器，否则走通用文本提取。
2. 为文档补齐标题、来源 URL、抓取时间等元信息。
3. 将结果封装为 Document 列表供索引管线消费。
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin
from datetime import datetime

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.readers.base import BasePydanticReader
from llama_index.core.schema import Document

logger = logging.getLogger(__name__)


def _mpweixin_reader(soup: Any, **kwargs) -> Tuple[str, Dict[str, Any]]:
    """
    针对微信公众号页面提取正文与元信息。

    Args:
        soup: BeautifulSoup 解析对象。
        **kwargs: 兼容保留参数。

    Returns:
        Tuple[str, Dict[str, Any]]: 正文文本与扩展元信息。
    """
    meta_tag_title = soup.find('meta', attrs={'property': 'og:title'})
    title = meta_tag_title['content']
    extra_info = {
        "title": title,
        #"Author": soup.select_one("span #js_author_name").getText(),
    }
    text = soup.select_one("div #page-content").getText()
    return text, extra_info


DEFAULT_WEBSITE_EXTRACTOR: Dict[
    str, Callable[[Any, str], Tuple[str, Dict[str, Any]]]
] = {
    "mp.weixin.qq.com": _mpweixin_reader,
}


class BeautifulSoupWebReader(BasePydanticReader):
    """BeautifulSoup web page reader.

    Reads pages from the web.
    Requires the `bs4` and `urllib` packages.

    Args:
        website_extractor (Optional[Dict[str, Callable]]): A mapping of website
            hostname (e.g. google.com) to a function that specifies how to
            extract text from the BeautifulSoup obj. See DEFAULT_WEBSITE_EXTRACTOR.
    """

    is_remote: bool = True
    _website_extractor: Dict[str, Callable] = PrivateAttr()

    def __init__(self, website_extractor: Optional[Dict[str, Callable]] = None) -> None:
        """
        初始化网页读取器。

        Args:
            website_extractor: 自定义站点提取器映射；为空时使用默认映射。
        """
        super().__init__()
        self._website_extractor = website_extractor or DEFAULT_WEBSITE_EXTRACTOR

    @classmethod
    def class_name(cls) -> str:
        """
        返回类名标识。

        Returns:
            str: 读取器类名。
        """
        return "BeautifulSoupWebReader"

    def load_data(
        self,
        urls: List[str],
        custom_hostname: Optional[str] = None,
        include_url_in_text: Optional[bool] = True,
    ) -> List[Document]:
        """
        从 URL 列表抓取网页并转换为 Document 列表。

        Args:
            urls: 待抓取 URL 列表。
            custom_hostname: 强制指定 hostname（用于自定义域名映射）。
            include_url_in_text: 是否在正文中保留 URL（透传给站点提取器）。

        Returns:
            List[Document]: 可直接用于摄取管线的文档列表。

        Raises:
            ValueError: URL 无法抓取或解析失败时抛出。
        """
        from urllib.parse import urlparse

        import requests
        from bs4 import BeautifulSoup

        documents = []
        for url in urls:
            try:
                page = requests.get(url)
                hostname = custom_hostname or urlparse(url).hostname or ""

                soup = BeautifulSoup(page.content, "html.parser")

                data = ""
                extra_info = {
                    "title": soup.select_one("title"),
                    "url_source": url,
                    "creation_date": datetime.now().date().isoformat(),
                }
                if hostname in self._website_extractor:
                    data, metadata = self._website_extractor[hostname](
                        soup=soup, url=url, include_url_in_text=include_url_in_text
                    )
                    extra_info.update(metadata)

                else:
                    data = soup.getText()

                documents.append(Document(text=data, id_=url, extra_info=extra_info))
            except Exception:
                print(f"Could not scrape {url}")
                raise ValueError(f"One of the inputs is not a valid url: {url}")

        return documents
