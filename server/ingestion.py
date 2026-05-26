"""
模块功能：
- 封装文档摄取（ingestion）流程，统一文本切分、向量化和中文标题增强。

执行逻辑：
1. 从全局 Settings 中读取 embedding 与 text splitter。
2. 组装 AdvancedIngestionPipeline 的 transformations。
3. 在 run 时执行父类管线并返回节点集合。

关键依赖：
- llama_index.core.ingestion.IngestionPipeline
- server.splitters.ChineseTitleExtractor
- server.stores.strage_context / ingestion_cache
"""

from llama_index.core import Settings
from llama_index.core.ingestion import IngestionPipeline, DocstoreStrategy
from server.splitters import ChineseTitleExtractor
from server.stores.strage_context import STORAGE_CONTEXT
from server.stores.ingestion_cache import INGESTION_CACHE


class AdvancedIngestionPipeline(IngestionPipeline):
    def __init__(
        self,
    ):
        """
        功能：
        - 初始化高级摄取管线，绑定统一的转换链和存储策略。

        输入：
        - 无显式参数，依赖全局 Settings 与存储上下文。

        执行逻辑：
        1. 读取全局 embedding model 与 text splitter。
        2. 注入中文标题增强转换器。
        3. 绑定 docstore、vector_store、cache 与 upsert 策略。

        输出：
        - 完成初始化的 AdvancedIngestionPipeline 实例。
        """
        embed_model = Settings.embed_model
        text_splitter = Settings.text_splitter

        super().__init__(
            transformations=[
                text_splitter,
                embed_model,
                ChineseTitleExtractor(),  # 中文标题增强，提升分块语义质量。
            ],
            docstore=STORAGE_CONTEXT.docstore,
            vector_store=STORAGE_CONTEXT.vector_store,
            cache=INGESTION_CACHE,
            docstore_strategy=DocstoreStrategy.UPSERTS,
        )

    def run(self, documents):
        """
        功能：
        - 执行文档摄取并返回可入库节点。

        输入：
        - documents(list): 文档对象列表。

        执行逻辑：
        1. 输出输入文档数量用于调试。
        2. 调用父类 run 执行转换、向量化、缓存处理。
        3. 输出生成节点数量并返回。

        输出：
        - list: 处理后的节点集合。
        """
        print(f"Load {len(documents)} Documents")
        nodes = super().run(documents=documents)
        print(f"Ingested {len(nodes)} Nodes")
        return nodes