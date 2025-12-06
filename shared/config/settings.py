"""
Settings Module
===============

Pydantic-based configuration with environment variable loading.

Version: 0.1.0
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    CLAUDE = "claude"
    OPENAI = "openai"
    OLLAMA = "ollama"


class BlockchainMode(str, Enum):
    """Blockchain operation mode."""

    MOCK = "mock"
    TESTNET = "testnet"
    MAINNET = "mainnet"


class PostgresSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = "localhost"
    port: int = 5432
    user: str = "civium"
    password: SecretStr = SecretStr("civium_dev_password")
    db: str = "civium"

    @property
    def async_url(self) -> str:
        """Generate async SQLAlchemy connection URL."""
        pwd = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pwd}@{self.host}:{self.port}/{self.db}"

    @property
    def sync_url(self) -> str:
        """Generate sync SQLAlchemy connection URL."""
        pwd = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pwd}@{self.host}:{self.port}/{self.db}"


class Neo4jSettings(BaseSettings):
    """Neo4j graph database configuration."""

    model_config = SettingsConfigDict(env_prefix="NEO4J_")

    host: str = "localhost"
    bolt_port: int = Field(default=7687, alias="NEO4J_BOLT_PORT")
    http_port: int = Field(default=7474, alias="NEO4J_HTTP_PORT")
    user: str = "neo4j"
    password: SecretStr = SecretStr("civium_graph_password")

    @property
    def uri(self) -> str:
        """Generate Neo4j Bolt URI."""
        return f"bolt://{self.host}:{self.bolt_port}"


class MongoSettings(BaseSettings):
    """MongoDB configuration."""

    model_config = SettingsConfigDict(env_prefix="MONGODB_")

    host: str = "localhost"
    port: int = 27017
    user: str = "civium"
    password: SecretStr = SecretStr("civium_mongo_password")
    db: str = Field(default="civium_regulations", alias="MONGODB_DB")

    @property
    def uri(self) -> str:
        """Generate MongoDB connection URI."""
        pwd = self.password.get_secret_value()
        return f"mongodb://{self.user}:{pwd}@{self.host}:{self.port}/{self.db}?authSource=admin"


class RedisSettings(BaseSettings):
    """Redis cache configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: SecretStr = SecretStr("civium_redis_password")
    db: int = 0

    @property
    def url(self) -> str:
        """Generate Redis connection URL."""
        pwd = self.password.get_secret_value()
        return f"redis://:{pwd}@{self.host}:{self.port}/{self.db}"


class InfluxSettings(BaseSettings):
    """InfluxDB time-series configuration."""

    model_config = SettingsConfigDict(env_prefix="INFLUXDB_")

    host: str = "localhost"
    port: int = 8086
    token: SecretStr = SecretStr("civium_influx_token_change_me")
    org: str = "civium"
    bucket: str = "compliance_metrics"

    @property
    def url(self) -> str:
        """Generate InfluxDB URL."""
        return f"http://{self.host}:{self.port}"


class KafkaSettings(BaseSettings):
    """Kafka event streaming configuration."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:9092"
    security_protocol: str = "PLAINTEXT"


class ClaudeSettings(BaseSettings):
    """Anthropic Claude API configuration."""

    model_config = SettingsConfigDict(env_prefix="CLAUDE_")

    api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="ANTHROPIC_API_KEY",
    )
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class OpenAISettings(BaseSettings):
    """OpenAI API configuration."""

    model_config = SettingsConfigDict(env_prefix="OPENAI_")

    api_key: SecretStr = SecretStr("")
    model: str = "gpt-4-turbo-preview"


class OllamaSettings(BaseSettings):
    """Ollama local LLM configuration."""

    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    host: str = "http://localhost:11434"
    model: str = "llama3.3:70b"


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: LLMProvider = LLMProvider.CLAUDE
    temperature: float = 0.1
    max_retries: int = 3
    timeout_seconds: int = 120

    # Provider-specific settings
    claude: ClaudeSettings = Field(default_factory=ClaudeSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)


class BlockchainSettings(BaseSettings):
    """Blockchain integration configuration."""

    model_config = SettingsConfigDict(env_prefix="BLOCKCHAIN_")

    mode: BlockchainMode = BlockchainMode.MOCK

    # Polygon/Ethereum settings (for testnet/mainnet)
    alchemy_api_key: SecretStr = SecretStr("")
    private_key: SecretStr = SecretStr("")
    audit_contract_address: str = ""
    did_registry_address: str = ""

    @property
    def rpc_url(self) -> str:
        """Generate RPC URL based on mode."""
        if self.mode == BlockchainMode.MOCK:
            return ""
        key = self.alchemy_api_key.get_secret_value()
        if self.mode == BlockchainMode.TESTNET:
            return f"https://polygon-mumbai.g.alchemy.com/v2/{key}"
        return f"https://polygon-mainnet.g.alchemy.com/v2/{key}"


class JWTSettings(BaseSettings):
    """JWT authentication configuration."""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: SecretStr = SecretStr("your-jwt-secret-key-min-32-chars-long")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")

    enabled: bool = True
    requests_per_minute: int = 100
    burst: int = 20


class CORSSettings(BaseSettings):
    """CORS configuration."""

    model_config = SettingsConfigDict(env_prefix="CORS_")

    origins: str = "http://localhost:3000,http://localhost:5173"
    allow_credentials: bool = True

    @property
    def origins_list(self) -> list[str]:
        """Parse origins string into list."""
        return [o.strip() for o in self.origins.split(",") if o.strip()]


class ServicePorts(BaseSettings):
    """Service port configuration."""

    regulatory_intelligence: int = Field(default=8001, alias="REGULATORY_INTELLIGENCE_PORT")
    compliance_graph: int = Field(default=8002, alias="COMPLIANCE_GRAPH_PORT")
    entity_assessment: int = Field(default=8003, alias="ENTITY_ASSESSMENT_PORT")
    verification: int = Field(default=8004, alias="VERIFICATION_PORT")
    monitoring: int = Field(default=8005, alias="MONITORING_PORT")
    api_gateway: int = Field(default=8000, alias="API_GATEWAY_PORT")


class Settings(BaseSettings):
    """
    Main application settings.

    Loads configuration from environment variables with sensible defaults.
    Use the global `settings` singleton or call `get_settings()`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    log_level: LogLevel = LogLevel.INFO
    secret_key: SecretStr = SecretStr("your-super-secret-key-change-in-production")

    # Project paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # Service ports
    ports: ServicePorts = Field(default_factory=ServicePorts)

    # Database connections
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)
    mongodb: MongoSettings = Field(default_factory=MongoSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    influxdb: InfluxSettings = Field(default_factory=InfluxSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)

    # LLM configuration
    llm: LLMSettings = Field(default_factory=LLMSettings)

    # Blockchain configuration
    blockchain: BlockchainSettings = Field(default_factory=BlockchainSettings)

    # Authentication
    jwt: JWTSettings = Field(default_factory=JWTSettings)

    # Security
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)

    # Monitoring
    prometheus_enabled: bool = True
    otel_enabled: bool = True
    otel_service_name: str = "civium"

    @field_validator("log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, v: str | LogLevel) -> LogLevel:
        """Ensure log level is uppercase."""
        if isinstance(v, str):
            return LogLevel(v.upper())
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        """Check if running in test mode."""
        return self.environment == Environment.TESTING


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Application settings singleton.
    """
    return Settings()
