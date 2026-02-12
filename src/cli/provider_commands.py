"""
LLM provider info CLI commands.
"""

from src.llm_provider import get_provider_info


def register_provider_commands(subparsers):
    """Register provider subcommands."""
    subparsers.add_parser("provider-info", help="Show LLM provider status and availability.")


def handle_provider_info(config, args):
    """Show current provider, model, status, availability."""
    info_list = get_provider_info(config)
    current = config.get("llm", {}).get("provider", "mock")

    print(f"\nCurrent provider: {current}")
    print(f"\n{'Key':<20} {'Label':<30} {'Available':<10} {'Reason'}")
    print(f"{'---':<20} {'---':<30} {'---':<10} {'---'}")

    for info in info_list:
        marker = "*" if info["key"] == current else " "
        avail = "Yes" if info["available"] else "No"
        reason = info.get("reason", "")
        print(f"{marker}{info['key']:<19} {info['label']:<30} {avail:<10} {reason}")
