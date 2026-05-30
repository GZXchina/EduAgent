from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 服务
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./database/eduagent.db"
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 讯飞星火
    spark_api_type: str = "websocket"
    spark_app_id: str = ""
    spark_api_key: str = ""
    spark_api_secret: str = ""
    spark_api_password: str = ""
    spark_ws_url: str = "wss://spark-api.xf-yun.com/v4.0/chat"
    spark_domain: str = "4.0Ultra"
    spark_api_url: str = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    spark_model: str = "generalv3.5"
    spark_timeout: float = 120.0

    # 讯飞ASR语音识别
    asr_app_id: str = ""
    asr_api_key: str = ""
    asr_api_secret: str = ""
    asr_ws_url: str = "wss://raasr.xfyun.cn/v2/recognize"

    # 讯飞TTS语音合成
    tts_app_id: str = ""
    tts_api_key: str = ""
    tts_api_secret: str = ""
    tts_ws_url: str = "wss://tts-api.xfyun.cn/v2/tts"

    # RAG
    knowledge_dir: str = "./knowledge"
    chroma_persist_dir: str = "./vector_db/chroma"
    chroma_collection: str = "eduagent_courses"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    chunk_size: int = 500
    chunk_overlap: int = 80
    rag_top_k: int = 4
    auto_ingest_on_startup: bool = False

    profile_cache_ttl: int = 3600

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def spark_configured(self) -> bool:
        ws_ok = bool(self.spark_app_id and self.spark_api_key and self.spark_api_secret)
        http_ok = bool(self.spark_app_id and self.spark_api_key and self.spark_api_secret and self.spark_api_url)
        return ws_ok or http_ok


@lru_cache
def get_settings() -> Settings:
    return Settings()
