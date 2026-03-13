"""
Configuration utilities for QuizWeaver web frontend.
"""

import os

import yaml


def save_api_key_to_env(key_name, value, env_path=None):
    """Write an API key to the .env file (gitignored), never to config.yaml.

    Updates existing key or appends new one.
    """
    if env_path is None:
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        env_path = os.path.abspath(env_path)

    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key_name}="):
                lines[i] = f"{key_name}={value}\n"
                found = True
                break

    if not found:
        lines.append(f"{key_name}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)


def save_config(config, config_path="config.yaml"):
    """
    Write the config dict back to config.yaml.

    Includes a safety guard: refuses to write if the database_file path
    points to a temp directory. This prevents test fixtures (which use
    temp DB files) from accidentally corrupting config.yaml when a route
    calls save_config without patching it.

    Args:
        config: Application config dict to persist
        config_path: Path to config file (default: config.yaml)
    """
    import tempfile

    # Safety guard: never persist temp DB paths to config.yaml
    db_path = config.get("paths", {}).get("database_file", "")
    temp_dir = tempfile.gettempdir().lower()
    if db_path and os.path.isabs(db_path) and db_path.lower().startswith(temp_dir):
        import logging

        logging.getLogger(__name__).warning(
            "save_config blocked: database_file points to temp directory (%s). "
            "This usually means a test is running without patching save_config.",
            db_path,
        )
        return

    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
