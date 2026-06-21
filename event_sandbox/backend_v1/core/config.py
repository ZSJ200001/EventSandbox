"""统一配置管理，支持环境变量与 .env 文件。

使用 pydantic-settings 单点管理所有配置项，消除散落在各模块的 os.getenv。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """应用全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 服务
    app_name: str = Field(default="EventSandbox API", description="应用名称")
    app_version: str = Field(default="1.1.0", description="应用版本")
    port: int = Field(default=8000, description="服务端口")
    host: str = Field(default="0.0.0.0", description="绑定地址")

    # LLM
    # llm_api_base: str = Field(
    #     default="http://101.251.216.47/8411/v1",  # Qwen3-Coder-Next
    #     description="OpenAI 兼容接口地址",
    # )
    llm_api_base: str = Field(
        default="http://101.251.216.48/9565/v1",    # Qwen3.6-27B
        description="OpenAI 兼容接口地址",
    )
    llm_api_key: str = Field(default="sk-empty", description="LLM API 密钥")
    # default_model: str = Field(default="Qwen3-Coder-Next", description="默认模型")
    default_model: str = Field(default="Qwen3.6-27B", description="默认模型")
    llm_timeout: float = Field(default=120.0, description="LLM 请求超时（秒）")
    llm_max_tokens: int = Field(default=2048, description="单次请求最大 Token")
    llm_temperature: float = Field(default=0.7, description="采样温度")
    llm_enable_few_shot: bool = Field(default=True, description="是否启用 Few-shot")
    llm_max_retries: int = Field(default=3, description="LLM 调用失败重试次数")
    llm_retry_delay: float = Field(default=1.0, description="重试间隔基数（秒）")

    # 推演
    simulation_max_rounds: int = Field(default=10, description="默认最大回合数")
    simulation_max_agents: int = Field(default=20, description="单推演最大 Agent 数")
    agent_max_short_term_memory: int = Field(default=20, description="Agent 短期记忆上限")
    agent_memory_archive_top_n: int = Field(default=3, description="溢出时归档前 N 条")

    # 实体构建并发控制
    entity_extract_max_rounds: int = Field(default=3, description="实体提取最大迭代轮数")
    entity_build_concurrency: int = Field(default=5, description="实体属性构建并发数上限，防止LLM超限")

    # 新闻向量检索
    news_retrieval_enabled: bool = Field(default=True, description="是否启用新闻检索")
    news_hybase_database: str = Field(default="system.event_database_trs_cn2", description="Hybase 新闻数据库名")
    news_hybase_host: str = Field(default="http://192.168.190.69:8555", description="Hybase 服务地址")
    news_hybase_key: str = Field(default="Trsadmin19940802.", description="Hybase 密钥")
    news_hybase_security_code: str = Field(default="Yu5iztekGyFOOp821JM8WQ==", description="Hybase 安全码")
    news_embedding_url: str = Field(default="http://101.251.216.48/embedding_bge/v1/embeddings", description="Embedding 服务地址")
    news_embedding_model: str = Field(default="bge-m3-vllm", description="Embedding 模型名")
    news_retrieval_topk: int = Field(default=10, description="向量检索返回条数")

    # 日志
    log_level: str = Field(default="INFO", description="日志级别")
    log_format: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        description="日志格式",
    )


# 全局单例（延迟初始化，便于测试时注入）
_settings: Settings | None = None


def get_settings() -> Settings:
    """获取全局配置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """重置配置（用于测试热重载场景）"""
    global _settings
    _settings = None
