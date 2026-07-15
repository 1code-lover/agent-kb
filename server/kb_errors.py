"""知识库通用异常类型。

本模块位于 server 层，供 server/utils、server/index 与 api/services 共同使用，避免
server -> api 的反向依赖。路由层根据这些稳定异常类型映射 HTTP 状态码。
"""


class KBServiceError(Exception):
    """知识库服务异常基类。"""

    def __init__(self, message: str, *, code: str = "kb_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class KBValidationError(KBServiceError):
    """参数、路径或输入数据校验失败。"""

    def __init__(self, message: str, *, code: str = "kb_validation_error"):
        super().__init__(message, code=code)


class KBNotFoundError(KBServiceError):
    """目标知识库不存在。"""

    def __init__(self, message: str, *, code: str = "kb_not_found"):
        super().__init__(message, code=code)


class KBConflictError(KBServiceError):
    """业务冲突，例如重复创建或删除非空知识库。"""

    def __init__(self, message: str, *, code: str = "kb_conflict"):
        super().__init__(message, code=code)


class KBUnavailableError(KBServiceError):
    """知识库存在但当前不可用。"""

    def __init__(self, message: str, *, code: str = "kb_unavailable"):
        super().__init__(message, code=code)


class KBConsistencyError(KBServiceError):
    """文件系统、registry 或索引补偿失败导致一致性风险。"""

    def __init__(self, message: str, *, code: str = "kb_consistency_error"):
        super().__init__(message, code=code)
