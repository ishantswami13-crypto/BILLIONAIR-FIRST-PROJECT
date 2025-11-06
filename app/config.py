import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "devjwt")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///instance/dev.sqlite3")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PSP_PROVIDER = os.getenv("PSP_PROVIDER", "mock")
    FEATURE_FLAGS = {
        "UPI": bool(int(os.getenv("FEATURE_UPI", "1"))),
        "PAYROLL": bool(int(os.getenv("FEATURE_PAYROLL", "0"))),
    }
