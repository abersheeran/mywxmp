from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # WeChat
    wechat_token: str
    app_id: str
    app_secret: str

    # Gemini
    gemini_pro_key: str
    gemini_pro_url: str
    gemini_pro_vision_url: str


settings = Settings.model_validate({})
