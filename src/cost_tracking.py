"""
Cost tracking infrastructure for QuizWeaver.

Logs API calls, tracks costs, and enforces rate limits to prevent
accidental overspending when using real LLM providers.
"""

import os
from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple

# Pricing table (per 1M tokens) for known models
MODEL_PRICING = {
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash-exp": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-3-flash-preview": {"input": 0.15, "output": 0.60},
    "gemini-3-pro-preview": {"input": 1.25, "output": 10.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
}

DEFAULT_LOG_FILE = "api_costs.log"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate cost based on model pricing table.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in dollars
    """
    pricing = MODEL_PRICING.get(model, {"input": 0.15, "output": 0.60})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def log_api_call(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost: Optional[float] = None,
    log_file: str = DEFAULT_LOG_FILE,
) -> bool:
    """
    Log an API call to the cost tracking log file.

    Args:
        provider: Provider name (e.g., "gemini", "vertex")
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost: Cost in dollars (auto-estimated if None)
        log_file: Path to log file

    Returns:
        True on success
    """
    if cost is None:
        cost = estimate_cost(model, input_tokens, output_tokens)

    timestamp = datetime.now().isoformat()
    line = f"{timestamp} | {provider} | {model} | {input_tokens} | {output_tokens} | ${cost:.6f}\n"

    try:
        with open(log_file, "a") as f:
            f.write(line)
        return True
    except Exception as e:
        print(f"Warning: Could not log API cost: {e}")
        return False


def get_cost_summary(log_file: str = DEFAULT_LOG_FILE) -> Dict[str, Any]:
    """
    Read and aggregate costs from the log file.

    Args:
        log_file: Path to log file

    Returns:
        Dict with aggregated stats:
            total_calls, total_cost, total_input_tokens, total_output_tokens,
            by_provider, by_day
    """
    summary = {
        "total_calls": 0,
        "total_cost": 0.0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "by_provider": {},
        "by_day": {},
    }

    if not os.path.exists(log_file):
        return summary

    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 6:
                    continue

                timestamp_str = parts[0]
                provider = parts[1]
                _model = parts[2]  # noqa: F841
                input_tokens = int(parts[3])
                output_tokens = int(parts[4])
                cost = float(parts[5].replace("$", ""))

                summary["total_calls"] += 1
                summary["total_cost"] += cost
                summary["total_input_tokens"] += input_tokens
                summary["total_output_tokens"] += output_tokens

                # By provider
                if provider not in summary["by_provider"]:
                    summary["by_provider"][provider] = {"calls": 0, "cost": 0.0}
                summary["by_provider"][provider]["calls"] += 1
                summary["by_provider"][provider]["cost"] += cost

                # By day
                try:
                    day = timestamp_str[:10]  # YYYY-MM-DD
                    if day not in summary["by_day"]:
                        summary["by_day"][day] = {"calls": 0, "cost": 0.0}
                    summary["by_day"][day]["calls"] += 1
                    summary["by_day"][day]["cost"] += cost
                except (ValueError, IndexError):
                    pass

    except Exception as e:
        print(f"Warning: Could not read cost log: {e}")

    return summary


def check_rate_limit(config: dict, log_file: str = DEFAULT_LOG_FILE) -> Tuple[bool, int, float]:
    """
    Check if rate limits have been exceeded.

    Args:
        config: Application config dict
        log_file: Path to cost log file

    Returns:
        Tuple of (is_limit_exceeded, remaining_calls, remaining_budget)
    """
    llm_config = config.get("llm", {})
    max_calls = llm_config.get("max_calls_per_session", 50)
    max_cost = llm_config.get("max_cost_per_session", 5.00)

    summary = get_cost_summary(log_file)

    remaining_calls = max(0, max_calls - summary["total_calls"])
    remaining_budget = max(0.0, max_cost - summary["total_cost"])

    is_exceeded = remaining_calls <= 0 or remaining_budget <= 0
    return is_exceeded, remaining_calls, remaining_budget


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text using character-based heuristic.

    Gemini models average ~4 characters per token for English text.

    Args:
        text: Input text string

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    # ~4 chars per token is a reasonable approximation for English text
    return max(1, len(text) // 4)


def summarize_lesson_context(lesson_logs: list, assumed_knowledge: dict, max_chars: int = 2000) -> str:
    """
    Summarize lesson context to reduce token count in prompts.

    Args:
        lesson_logs: List of lesson log dicts with 'date' and 'topics' keys
        assumed_knowledge: Dict of {topic: {depth, ...}}
        max_chars: Maximum character length for the summary

    Returns:
        Concise string summary of lesson context
    """
    parts = []

    if lesson_logs:
        parts.append("Recent lessons:")
        for log in lesson_logs[:10]:
            topics = log.get("topics", [])
            if topics:
                parts.append(f"  {log.get('date', '?')}: {', '.join(topics)}")

    if assumed_knowledge:
        parts.append("Knowledge depths:")
        depth_labels = {1: "intro", 2: "reinf", 3: "pract", 4: "mast", 5: "expert"}
        for topic, data in assumed_knowledge.items():
            depth = data.get("depth", 1)
            parts.append(f"  {topic}: {depth_labels.get(depth, '?')}")

    summary = "\n".join(parts)
    if len(summary) > max_chars:
        truncation_marker = "\n... (truncated)"
        summary = summary[: max_chars - len(truncation_marker)] + truncation_marker

    return summary


def estimate_pipeline_cost(config: dict, max_retries: int = 3) -> Dict[str, Any]:
    """
    Estimate the cost of running the full agent pipeline.

    The pipeline makes 2 LLM calls per attempt (generator + critic),
    up to max_retries attempts. This estimates the worst-case cost.

    Args:
        config: Application config dict
        max_retries: Maximum retry attempts (from agent_loop config)

    Returns:
        Dict with:
            model, calls_per_attempt, max_attempts, max_calls,
            estimated_cost_per_call, estimated_max_cost, provider
    """
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "mock")

    # Look up the default model from provider registry
    try:
        from src.llm_provider import PROVIDER_REGISTRY

        registry_default = PROVIDER_REGISTRY.get(provider, {}).get(
            "default_model", "gemini-2.5-flash"
        )
    except ImportError:
        registry_default = "gemini-2.5-flash"
    model = llm_config.get("model_name") or registry_default

    if provider == "mock":
        return {
            "provider": "mock",
            "model": model,
            "calls_per_attempt": 2,
            "max_attempts": max_retries,
            "max_calls": max_retries * 2,
            "estimated_cost_per_call": 0.0,
            "estimated_max_cost": 0.0,
        }

    # Estimate ~2000 input tokens and ~1000 output tokens per call
    avg_input = 2000
    avg_output = 1000
    cost_per_call = estimate_cost(model, avg_input, avg_output)
    calls_per_attempt = 2  # generator + critic
    max_calls = max_retries * calls_per_attempt

    return {
        "provider": provider,
        "model": model,
        "calls_per_attempt": calls_per_attempt,
        "max_attempts": max_retries,
        "max_calls": max_calls,
        "estimated_cost_per_call": cost_per_call,
        "estimated_max_cost": cost_per_call * max_calls,
    }


def get_monthly_total(
    log_file: str = DEFAULT_LOG_FILE,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Get cost totals for a specific month.

    Args:
        log_file: Path to log file
        year: Year (defaults to current year)
        month: Month 1-12 (defaults to current month)

    Returns:
        Dict with calls, cost, input_tokens, output_tokens for the month
    """
    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    prefix = f"{year}-{month:02d}"
    result = {"calls": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0}

    if not os.path.exists(log_file):
        return result

    try:
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 6:
                    continue
                if not parts[0].startswith(prefix):
                    continue
                result["calls"] += 1
                result["input_tokens"] += int(parts[3])
                result["output_tokens"] += int(parts[4])
                result["cost"] += float(parts[5].replace("$", ""))
    except Exception:
        pass

    return result


def check_budget(config: dict, log_file: str = DEFAULT_LOG_FILE) -> Dict[str, Any]:
    """
    Check monthly budget status.

    Args:
        config: Application config dict (reads llm.monthly_budget)
        log_file: Path to cost log file

    Returns:
        Dict with: budget, spent, remaining, percent_used, exceeded, warning
    """
    budget = float(config.get("llm", {}).get("monthly_budget", 0))
    monthly = get_monthly_total(log_file)
    spent = monthly["cost"]

    if budget <= 0:
        return {
            "budget": 0,
            "spent": spent,
            "remaining": 0,
            "percent_used": 0,
            "exceeded": False,
            "warning": False,
            "enabled": False,
        }

    remaining = max(0.0, budget - spent)
    percent_used = min(100, (spent / budget) * 100) if budget > 0 else 0

    return {
        "budget": budget,
        "spent": spent,
        "remaining": remaining,
        "percent_used": percent_used,
        "exceeded": spent >= budget,
        "warning": percent_used >= 80,
        "enabled": True,
    }


def format_cost_report(stats: Dict[str, Any]) -> str:
    """
    Format cost summary stats for CLI display.

    Args:
        stats: Dict from get_cost_summary()

    Returns:
        Formatted string for display
    """
    lines = []
    lines.append("=== API Cost Summary ===")
    lines.append(f"Total API calls: {stats['total_calls']}")
    lines.append(f"Total cost: ${stats['total_cost']:.4f}")
    lines.append(f"Total input tokens: {stats['total_input_tokens']:,}")
    lines.append(f"Total output tokens: {stats['total_output_tokens']:,}")

    if stats["by_provider"]:
        lines.append("\nBy Provider:")
        for provider, data in stats["by_provider"].items():
            lines.append(f"  {provider}: {data['calls']} calls, ${data['cost']:.4f}")

    if stats["by_day"]:
        lines.append("\nBy Day:")
        for day, data in sorted(stats["by_day"].items()):
            lines.append(f"  {day}: {data['calls']} calls, ${data['cost']:.4f}")

    if stats["total_cost"] > 5.0:
        lines.append("\n[WARNING] Total cost exceeds $5.00!")

    return "\n".join(lines)
