from flask import Flask
from .config import Config
from .extensions import db, migrate, jwt
from .api import register_api, register_errors
import os


def create_app(config_object: type[Config] | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    app.config.from_object(config_object or Config)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    register_api(app)
    register_errors(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    return app
