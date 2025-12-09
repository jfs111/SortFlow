"""ML Service Configuration"""
from pydantic_settings import BaseSettings
import torch

class Settings(BaseSettings):
    SERVICE_NAME: str = "SortFlow ML Service"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    DEVICE: str = "cpu"  # or "cuda" if GPU available
    DEFAULT_MODEL: str = "resnet50"
    EMBEDDING_DIM: int = 2048
    BATCH_SIZE: int = 32
    
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_IMAGES_PER_REQUEST: int = 10000
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.DEVICE == "auto":
            self.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

settings = Settings()