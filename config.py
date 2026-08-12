import os

# ============================================================
# 环境配置
# ============================================================
THINKRAG_ENV = os.getenv("THINKRAG_ENV", "development")
DEV_MODE = THINKRAG_ENV == "development"

# ============================================================
# 路径配置
# ============================================================
STORAGE_DIR = "storage"
DATA_DIR = "data"
MODEL_DIR = "localmodels"
CONFIG_STORE_FILE = "config_store.json"

# ============================================================
# 模型配置
# ============================================================

# 设备配置
LLM_DEVICE = "auto"
EMBEDDING_DEVICE = "auto"

# LLM 参数
TEMPERATURE = 0.1
TOP_K = 5
SYSTEM_PROMPT = "You are an AI assistant that helps users to find accurate information. You can answer questions, provide explanations, and generate text based on the input. Please answer the user's question exactly in the same language as the question or follow user's instructions. For example, if user's question is in Chinese, please generate answer in Chinese as well. If you don't know the answer, please reply the user that you don't know. If you need more information, you can ask the user for clarification. Please be professional to the user."
RESPONSE_MODE = ["compact", "refine", "tree_summarize", "simple_summarize", "accumulate", "compact_accumulate"]
DEFAULT_RESPONSE_MODE = "simple_summarize"

# Ollama 配置
OLLAMA_API_URL = "http://localhost:11434"

# API Keys（从环境变量读取）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY", "")
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# LLM 提供商列表
LLM_API_LIST = {
    "Ollama": {
        "api_base": OLLAMA_API_URL,
        "models": [],
        "provider": "Ollama",
    },
    "OpenAI": {
        "api_key": OPENAI_API_KEY,
        "api_base": "https://api.openai.com/v1/",
        "models": ["gpt-4", "gpt-3.5-turbo", "gpt-4o"],
        "provider": "OpenAI",
    },
    "DeepSeek": {
        "api_key": DEEPSEEK_API_KEY,
        "api_base": "https://api.deepseek.com/v1/",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "provider": "DeepSeek",
    },
    "Moonshot": {
        "api_key": MOONSHOT_API_KEY,
        "api_base": "https://api.moonshot.cn/v1/",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "provider": "Moonshot",
    },
    "Zhipu": {
        "api_key": ZHIPU_API_KEY,
        "api_base": "https://open.bigmodel.cn/api/paas/v4/",
        "models": ["glm-4-plus", "glm-4-0520", "glm-4", "glm-4-air", "glm-4-airx", "glm-4-long", "glm-4-flashx", "glm-4-flash", "glm-4v-plus", "glm-4v"],
        "provider": "Zhipu",
    },
}

# ============================================================
# 文本处理配置
# ============================================================
DEFAULT_CHUNK_SIZE = 2048
DEFAULT_CHUNK_OVERLAP = 512
ZH_TITLE_ENHANCE = False

# ============================================================
# 嵌入模型配置
# ============================================================
HF_ENDPOINT = "https://hf-mirror.com"
EMBEDDING_ALLOW_REMOTE_DOWNLOAD = os.getenv("EMBEDDING_ALLOW_REMOTE_DOWNLOAD", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

DEFAULT_EMBEDDING_MODEL = "bge-small-zh-v1.5"
EMBEDDING_MODEL_PATH = {
    "bge-small-zh-v1.5": "BAAI/bge-small-zh-v1.5",
    "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
}

# ============================================================
# 重排模型配置
# ============================================================
DEFAULT_RERANKER_MODEL = "bge-reranker-base"
RERANKER_MODEL_PATH = {
    "bge-reranker-base": "BAAI/bge-reranker-base",
    "bge-reranker-large": "BAAI/bge-reranker-large",
}

USE_RERANKER = False
RERANKER_MODEL_TOP_N = 2
RERANKER_MAX_LENGTH = 1024

# ============================================================
# 存储配置（按环境自动选择）
# ============================================================

# 外部服务地址（生产模式使用）
REDIS_URI = "redis://localhost:6379"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

# 向量数据库类型：chroma, lancedb, es
# 注意：开发模式（DEV_MODE=True）下此配置被忽略，强制使用 SimpleVectorStore
DEFAULT_VS_TYPE = "chroma"

# 文档存储类型：redis
# 注意：开发模式（DEV_MODE=True）下此配置被忽略，强制使用 SimpleDocumentStore
DEFAULT_DOC_STORE = "redis"

# 索引存储类型：redis
# 注意：开发模式（DEV_MODE=True）下此配置被忽略，强制使用 SimpleIndexStore
DEFAULT_INDEX_STORE = "redis"

# 聊天存储类型：redis, simple
# 注意：开发模式（DEV_MODE=True）下此配置被忽略，强制使用本地文件存储
DEFAULT_CHAT_STORE = "redis"

CHAT_STORE_FILE_NAME = "chat_store.json"
CHAT_STORE_KEY = "user1"

# 索引名称
DEFAULT_INDEX_NAME = "knowledge_base"

# ============================================================
# 安全配置（与环境无关，DEV_MODE=True 时仍然生效）
# 如需在开发模式下放宽限制，请修改 COMMAND_SECURITY 配置
# ============================================================

# 项目根目录（基于 config.py 文件位置，而非运行时 cwd）
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 命令安全配置
COMMAND_SECURITY = {
    # 危险命令黑名单（即使在白名单中也拒绝）
    "blacklist_patterns": [
        r"\brm\s+(-rf?|--recursive)\s+/",  # rm -rf /
        r"\bdd\s+",                          # dd 命令
        r"\bmkfs\b",                         # 格式化
        r"\bchmod\s+777\b",                  # 危险权限
        r">\s*/dev/sd",                      # 写入磁盘设备
        r"\bshutdown\b",
        r"\breboot\b",
    ],
    
    # 白名单命令（允许执行）
    "whitelist": [
        # 文件操作（只读）
        {"cmd": "ls", "risk": "low"},
        {"cmd": "cat", "risk": "low"},
        {"cmd": "head", "risk": "low"},
        {"cmd": "tail", "risk": "low"},
        {"cmd": "wc", "risk": "low"},
        {"cmd": "find", "risk": "medium", "args_pattern": r"^-.*\s+\.(/|\w)"},
        {"cmd": "grep", "risk": "low"},
        {"cmd": "echo", "risk": "low"},
        
        # Python 相关
        {"cmd": "python", "risk": "medium", "args_pattern": r"^-m\s+(pytest|unittest|pip|http\.server)"},
        {"cmd": "pip", "risk": "medium", "args_pattern": r"^(list|show|freeze)"},
        {"cmd": "pytest", "risk": "low"},
        
        # Git 操作（本地操作，不含 push/pull 等远程操作）
        # 注意：add/commit 允许提交文件，但不允许推送到远程仓库
        # 风险：Agent 可能提交敏感文件，但不会泄露到远程仓库
        {"cmd": "git", "risk": "medium", "args_pattern": r"^(status|log|diff|show|branch|add|commit)"},
        
        # 系统信息
        {"cmd": "pwd", "risk": "low"},
        {"cmd": "whoami", "risk": "low"},
        {"cmd": "date", "risk": "low"},
        {"cmd": "uname", "risk": "low"},
    ],
    
    # 命令链接符处理（管道、&&、||等）
    "allow_pipes": False,  # Phase 1: 禁用管道（shell=False 不支持管道）
    "allow_chaining": False,  # 禁止 && 和 ||
    
    # 命令超时配置（秒）
    "default_timeout": 30,  # 默认超时时间
    "tool_timeouts": {      # 特定命令的超时时间
        "pytest": 300,
        "pip": 120,
        "python": 120,
    },
}

# 路径安全配置
PATH_SECURITY = {
    # 文件读取允许的目录（使用项目根目录作为基准，避免路径漂移）
    "allowed_read_dirs": [
        os.path.join(_PROJECT_ROOT, "data"),
        os.path.join(_PROJECT_ROOT, "storage"),
        os.path.join(_PROJECT_ROOT, "localmodels"),
        os.path.join(_PROJECT_ROOT, "docs"),
    ],
    
    # 文件读取限制
    "max_file_size_mb": 10,      # 最大文件大小
    "allowed_extensions": [      # 允许的文件扩展名
        ".txt", ".md", ".json", ".csv", ".xml",
        ".py", ".js", ".ts", ".java", ".go", ".rs",
        ".html", ".css", ".yaml", ".yml", ".toml",
        ".pdf", ".docx", ".pptx", ".xlsx",
    ],
    
    # 符号链接处理
    "follow_symlinks": False,    # 是否允许跟随符号链接
}
