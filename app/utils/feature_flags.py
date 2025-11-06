from flask import current_app


def is_enabled(flag: str) -> bool:
    return current_app.config.get("FEATURE_FLAGS", {}).get(flag, False)
