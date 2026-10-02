from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "MeetGraph"
    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    MEETILY_BASE_URL: str = "http://127.0.0.1:8420"
    MEETILY_API_KEY: str = ""
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    SARVAM_BASE_URL: str = "https://api.sarvam.ai"
    SARVAM_API_KEY: str = ""
    SARVAM_MODEL: str = "saaras:v3"

    WAV2VEC2_MODEL: str = "facebook/wav2vec2-base-960h"
    
    DATABASE_URL: str = "sqlite:///./meetgraph.db"
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
