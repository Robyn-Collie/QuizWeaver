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

    Args:
        config: Application config dict to persist
        config_path: Path to config file (default: config.yaml)
    """
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
