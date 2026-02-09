"""
Configuration utilities for QuizWeaver web frontend.
"""

import yaml


def save_config(config, config_path="config.yaml"):
    """
    Write the config dict back to config.yaml.

    Args:
        config: Application config dict to persist
        config_path: Path to config file (default: config.yaml)
    """
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
