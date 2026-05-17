from pydantic_settings import BaseSettings
from pathlib import Path
from app.core.logging_config import logger
import base64
from pydantic import field_validator
from functools import lru_cache



# this file for settings and configurations for the application
BASE_DIR = Path(__file__).parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # Database Settings (must match .env variable names)
    DATABASE_HOSTNAME: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "CarDealersPro"
    DATABASE_USERNAME: str = "postgres"
    DATABASE_PASSWORD: str  # No default value - fail fast if not set

    # JWT Settings
    ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # RSA Keys (base64 encoded environment variables for cloud deployment)
    PRIVATE_KEY_BASE64: str | None = None
    PUBLIC_KEY_BASE64: str | None = None

    # Key Paths (fallback for local development)
    BASE_DIR: Path = BASE_DIR
    PRIVATE_KEY_PATH: Path = BASE_DIR / "private.pem"
    PUBLIC_KEY_PATH: Path = BASE_DIR / "public.pem"

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @field_validator('DATABASE_PASSWORD')
    @classmethod
    def validate_database_password(cls, v: str) -> str:
        if not v or v == "your_password_here":
            raise ValueError('DATABASE_PASSWORD is required and must be set in .env file')
        return v

    @property # it's a property that returns a value
    @lru_cache(maxsize=None)  # Cache the result to avoid repeated disk I/O
    def private_key(self) -> str:
        if self.PRIVATE_KEY_BASE64:
            # Decode from base64 environment variable
            return base64.b64decode(self.PRIVATE_KEY_BASE64).decode('utf-8')
        else:
            # Fallback to file reading for local development
            return self.PRIVATE_KEY_PATH.read_text()

    @property # it's a property that returns a value
    @lru_cache(maxsize=None)  # Cache the result to avoid repeated disk I/O
    def public_key(self) -> str:
        if self.PUBLIC_KEY_BASE64:
            # Decode from base64 environment variable
            return base64.b64decode(self.PUBLIC_KEY_BASE64).decode('utf-8')
        else:
            # Fallback to file reading for local development
            return self.PUBLIC_KEY_PATH.read_text()

settings = Settings()



# Subscription limits per dealer plan
SUBSCRIPTION_LIMITS: dict[str, int] = {
    "FREE": 10,
    "SILVER": 50,
    "GOLD": 200,
    "PLATINUM": 1000,
}

# Allowed vehicle categories
VEHICLE_CATEGORIES: list[str] = [
    "car", "motorcycle", "truck", "van", "bus", "suv", "pickup"
] #  Add more vehicle categories

# Loan types supported by the platform
LOAN_TYPES: list[str] = ["New Car", "Used Car", "Refinance", "Corporate Loan"] #  Add more loan types

# Supported currencies
SUPPORTED_CURRENCIES: list[str] = ["EGP", "USD", "EUR"] #  Add more currencies

# Default finance configuration (used in loan calculations)
FINANCE_CONFIG: dict = {
    "default_interest_rates": {"new": 12.5, "used": 15.5},
    "default_min_down_payment": {"new": 15.0, "used": 30.0},
    "max_tenure_months": {"new": 84, "used": 60},
    "income_debt_ratio": 0.40,
} #  Add more finance configurations

# Inspector specializations
INSPECTOR_SPECIALIZATIONS: list[str] = [
    "Mechanic", "Body & Frame", "Electrical",
    "Interior & Detailing", "Transmission & Drivetrain", "Suspension Mechanic"
] #  Add more inspector specializations


if __name__ == "__main__":
    try:
        logger.info("--- Testing Configuration ---", extra={"request_id": "N/A"})
        logger.info(f"Algorithm: {settings.ALGORITHM}", extra={"request_id": "N/A"})
        logger.info(f"Private Key loaded (first 20 chars): {settings.private_key[:20]}...", extra={"request_id": "N/A"}) # means the first 20 characters of the private key
        logger.info(f"Public Key loaded (first 20 chars): {settings.public_key[:20]}...", extra={"request_id": "N/A"}) # means the first 20 characters of the public key
        logger.info(" Config is working perfectly!", extra={"request_id": "N/A"})
    except FileNotFoundError as e:
        logger.error(f" Error: Could not find the key file! {e}", extra={"request_id": "N/A"}) #this is a test file not a real request 
    except Exception as e:
        logger.error(f" An unexpected error occurred: {e}", extra={"request_id": "N/A"}) #this is a test file not a real request 
