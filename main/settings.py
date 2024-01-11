from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # WeChat
    wechat_token: str
    app_id: str
    app_secret: str
    wechat_id: str

    # Gemini
    gemini_pro_key: str
    gemini_pro_url: str
    gemini_pro_vision_url: str

    # GitHub
    github_webhook_secret: str


settings = Settings.model_validate({})
