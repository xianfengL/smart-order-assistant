from pathlib import Path
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    demo_mode: bool = True
    database_url: str = 'sqlite:///./data/orders.db'
    data_dir: Path = Path('data')
    jwt_secret: str = ''
    jwt_minutes: int = 120
    admin_password: str = ''
    customer_password: str = ''
    openai_api_key: str = ''
    openai_base_url: str = 'https://api.openai.com/v1'
    llm_model: str = ''
    embedding_model: str = 'text-embedding-3-small'
    chart_transport: str = 'local'
    cors_origins: str = 'http://localhost:5173,http://localhost:8080'

    def prepare(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.demo_mode:
            if not all([self.jwt_secret, self.admin_password, self.customer_password,
                        self.openai_api_key, self.llm_model]):
                raise ValueError('Live mode requires JWT_SECRET, ADMIN_PASSWORD, CUSTOMER_PASSWORD, OPENAI_API_KEY and LLM_MODEL')
            if len(self.jwt_secret) < 32:
                raise ValueError('JWT_SECRET must contain at least 32 characters')
        if not self.jwt_secret:
            secret_file = self.data_dir / '.jwt-secret'
            if not secret_file.exists():
                secret_file.write_text(secrets.token_urlsafe(48), encoding='utf-8')
            self.jwt_secret = secret_file.read_text(encoding='utf-8').strip()
        self.admin_password = self.admin_password or 'Admin123!'
        self.customer_password = self.customer_password or 'Demo123!'


settings = Settings()
