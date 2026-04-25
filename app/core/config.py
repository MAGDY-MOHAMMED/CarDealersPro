from pydantic_settings import BaseSettings
from pathlib import Path
from core.logging_config import logger

# this file for settings and configurations for the application
class Settings(BaseSettings):
    # Database Settings (must match .env variable names)
    DATABASE_HOSTNAME: str
    DATABASE_PORT: int
    DATABASE_NAME: str
    DATABASE_PASSWORD: str
    DATABASE_USERNAME: str
    
    # JWT Settings
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    # Key Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    PRIVATE_KEY_PATH: Path = BASE_DIR / "private.pem"
    PUBLIC_KEY_PATH: Path = BASE_DIR / "public.pem"
    
    class Config:
        env_file = ".env"

    @property # it's a property that returns a value
    def private_key(self) -> str:
        return self.PRIVATE_KEY_PATH.read_text()

    @property # it's a property that returns a value
    def public_key(self) -> str:
        return self.PUBLIC_KEY_PATH.read_text()

settings = Settings()

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