from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NEXTRADE API"
    environment: str = "development"
    # Public Binance Spot market data is read-only and does not need an API key.
    market_provider: str = "binance_public"
    market_data_api_key: str = ""
    allowed_origins: str = "*"
    economic_calendar_api_key: str = Field(default="", validation_alias=AliasChoices("FINNHUB_API_KEY", "ECONOMIC_CALENDAR_API_KEY"))
    demo_poll_seconds: int = 20
    calendar_poll_seconds: int = 300
    nextrade_db_path: str = "./nextrade_data.sqlite3"
    fcm_project_id: str = ""
    fcm_service_account_path: str = ""
    jwt_secret_key: str = Field(default="", validation_alias="NEXTRADE_JWT_SECRET")
    certificate_signing_key: str = Field(default="", validation_alias="NEXTRADE_CERTIFICATE_SIGNING_KEY")
    public_base_url: str = Field(default="", validation_alias="NEXTRADE_PUBLIC_BASE_URL")
    credential_encryption_key: str = Field(default="", validation_alias="NEXTRADE_CREDENTIAL_ENCRYPTION_KEY")
    # Default to demo billing until Google Play products and server verification are explicitly configured.
    billing_mode: str = Field(default="demo", validation_alias="NEXTRADE_BILLING_MODE")
    google_play_package_name: str = Field(default="", validation_alias="GOOGLE_PLAY_PACKAGE_NAME")
    google_play_service_account_path: str = Field(default="", validation_alias="GOOGLE_PLAY_SERVICE_ACCOUNT_PATH")
    google_play_pro_product_id: str = Field(default="nextrade_pro_monthly", validation_alias="GOOGLE_PLAY_PRO_PRODUCT_ID")
    google_play_premium_product_id: str = Field(default="nextrade_premium_monthly", validation_alias="GOOGLE_PLAY_PREMIUM_PRODUCT_ID")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def market_configured(self) -> bool:
        return self.market_provider.lower() == "binance_public"


settings = Settings()
