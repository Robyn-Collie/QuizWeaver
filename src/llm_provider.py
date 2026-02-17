import logging
import mimetypes
import os
import time
from abc import ABC, abstractmethod
from typing import Any

# API call audit log — captures exact payloads for transparency reporting
_api_audit_log = []


def get_api_audit_log():
    """Return the API audit log and clear it."""
    global _api_audit_log
    log = list(_api_audit_log)
    return log


def clear_api_audit_log():
    """Clear the API audit log."""
    global _api_audit_log
    _api_audit_log = []


def _log_api_call(
    provider_name, model, prompt_summary, response_summary, input_tokens=0, output_tokens=0, duration_ms=0, error=None
):
    """Log an API call for audit purposes."""
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "provider": provider_name,
        "model": model,
        "prompt_char_count": len(prompt_summary),
        "prompt_preview": prompt_summary[:500] + ("..." if len(prompt_summary) > 500 else ""),
        "response_char_count": len(response_summary),
        "response_preview": response_summary[:300] + ("..." if len(response_summary) > 300 else ""),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "error": error,
    }
    _api_audit_log.append(entry)
    logging.getLogger("quizweaver.api_audit").info(
        f"[API CALL] {provider_name}/{model} | "
        f"in={input_tokens} out={output_tokens} | {duration_ms}ms | "
        f"prompt={len(prompt_summary)} chars"
    )


# Check if google-genai SDK is available (lazy import in provider classes)
try:
    from google import genai as _genai_module

    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

try:
    import anthropic as _anthropic_module

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


class ProviderError(Exception):
    """Raised when an LLM provider fails with a user-understandable error.

    Attributes:
        user_message: A plain-English message suitable for displaying to teachers
            via flash() or CLI output. Always includes actionable guidance.
        provider_name: Which provider triggered the error (e.g., "gemini").
        error_code: Optional HTTP status or error classification for programmatic use.
    """

    def __init__(self, user_message: str, provider_name: str = "", error_code: str = ""):
        self.user_message = user_message
        self.provider_name = provider_name
        self.error_code = error_code
        super().__init__(user_message)


def _classify_provider_error(e: Exception, provider_name: str) -> ProviderError:
    """Convert a raw provider exception into a ProviderError with actionable guidance."""
    msg = str(e)
    lower = msg.lower()

    if "401" in msg or "unauthorized" in lower or ("invalid" in lower and "key" in lower):
        return ProviderError(
            f"Authentication failed for {provider_name}. Your API key may be incorrect or expired. "
            "Go to Settings > Setup Wizard to update it.",
            provider_name=provider_name,
            error_code="auth",
        )
    if "403" in msg or "forbidden" in lower or "permission" in lower:
        return ProviderError(
            f"Access denied by {provider_name}. Your API key may not have permission for this model. "
            "Check your provider account settings or try a different model.",
            provider_name=provider_name,
            error_code="permission",
        )
    if "404" in msg or "not found" in lower:
        return ProviderError(
            f"Model not found on {provider_name}. The model name may be incorrect or unavailable in your region. "
            "Go to Settings to check the model name.",
            provider_name=provider_name,
            error_code="not_found",
        )
    if "429" in msg or "rate" in lower or "quota" in lower or "resource" in lower and "exhaust" in lower:
        return ProviderError(
            f"Rate limit or quota exceeded on {provider_name}. Wait a moment and try again, "
            "or check your billing/quota at your provider's dashboard.",
            provider_name=provider_name,
            error_code="rate_limit",
        )
    if "timeout" in lower or "timed out" in lower or "deadline" in lower:
        return ProviderError(
            f"{provider_name} took too long to respond. Check your internet connection and try again. "
            "For large quizzes, consider reducing the question count.",
            provider_name=provider_name,
            error_code="timeout",
        )
    if "connection" in lower or "refused" in lower or "unreachable" in lower or "dns" in lower:
        return ProviderError(
            f"Could not connect to {provider_name}. Check your internet connection. "
            "If using a local provider (Ollama), make sure it is running.",
            provider_name=provider_name,
            error_code="connection",
        )
    if "billing" in lower or "payment" in lower:
        return ProviderError(
            f"Billing issue with {provider_name}. Check that your account has an active payment method "
            "and sufficient credits.",
            provider_name=provider_name,
            error_code="billing",
        )

    # Fallback: include the raw error but wrap it in guidance
    return ProviderError(
        f"{provider_name} error: {msg}. "
        "If this persists, try switching to a different provider in Settings, "
        "or use Mock mode for cost-free testing.",
        provider_name=provider_name,
        error_code="unknown",
    )


class LLMProvider(ABC):
    """
    Abstract base class for a generic LLM provider.
    This defines the interface that all concrete providers must implement.
    """

    @abstractmethod
    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generates content based on a list of prompt parts (text and images).

        Args:
            prompt_parts (list): A list containing strings and/or image objects.
            json_mode (bool): Whether to force JSON output.

        Returns:
            str: The generated text from the language model.
        """
        pass

    @abstractmethod
    def prepare_image_context(self, image_path: str) -> Any:
        """
        Prepares an image from a file path into a format suitable for the LLM's generate method.
        This abstracts away provider-specific image handling (e.g., uploading, converting).

        Args:
            image_path (str): The path to the image file.

        Returns:
            Any: A representation of the image context understood by the provider's generate method.
        """
        pass


class GeminiProvider(LLMProvider):
    """
    Concrete implementation of the LLMProvider for Google's Gemini models
    using the unified google-genai SDK.
    Handles both Gemini Flash and Gemini Pro — model is specified per-instance.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Gemini provider with API credentials.

        Args:
            api_key: Google Gemini API key for authentication
            model_name: Name of the Gemini model to use (default: gemini-2.5-flash)
        """
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self._model_name = model_name

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using the Gemini API.

        Args:
            prompt_parts: List of prompt components (text strings and/or image objects)
            json_mode: If True, configures the model to return JSON-formatted output

        Returns:
            Generated text response from the model, or empty JSON array on error
        """
        start_time = time.time()
        prompt_text = " ".join(str(p) for p in prompt_parts if isinstance(p, str))
        try:
            config = {}
            if json_mode:
                config["response_mime_type"] = "application/json"

            response = self.client.models.generate_content(
                model=self._model_name,
                contents=prompt_parts,
                config=config if config else None,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            input_tokens = 0
            output_tokens = 0

            # Log cost if token metadata available
            try:
                from src.cost_tracking import log_api_call

                usage = getattr(response, "usage_metadata", None)
                if usage:
                    input_tokens = getattr(usage, "prompt_token_count", 0)
                    output_tokens = getattr(usage, "candidates_token_count", 0)
                    log_api_call(
                        "gemini",
                        self._model_name,
                        input_tokens,
                        output_tokens,
                    )
            except Exception:
                pass

            result_text = response.text
            _log_api_call(
                "gemini", self._model_name, prompt_text, result_text, input_tokens, output_tokens, duration_ms
            )
            return result_text
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            _log_api_call("gemini", self._model_name, prompt_text, "", 0, 0, duration_ms, error=str(e))
            raise _classify_provider_error(e, "Gemini") from e

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Upload an image file to Gemini API for use in multimodal prompts.

        Args:
            image_path: Path to the image file to upload

        Returns:
            Gemini file object that can be passed to generate()
        """
        return self.client.files.upload(file=image_path)


class VertexAIProvider(LLMProvider):
    """
    Concrete implementation of the LLMProvider for Google Cloud Vertex AI models
    using the unified google-genai SDK with vertexai=True.
    """

    def __init__(self, project_id: str, location: str, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Vertex AI provider with Google Cloud credentials.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., 'us-central1')
            model_name: Name of the Vertex AI model to use (default: gemini-2.5-flash)

        Raises:
            ImportError: If google-genai is not installed
        """
        if not _GENAI_AVAILABLE:
            raise ImportError("The Google AI library is not installed. Run: pip install google-genai")

        from google import genai

        self.client = genai.Client(vertexai=True, project=project_id, location=location)
        self._model_name = model_name

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using the Vertex AI API.

        Args:
            prompt_parts: List of prompt components (text strings and/or image objects)
            json_mode: If True, configures the model to return JSON-formatted output

        Returns:
            Generated text response from the model, or empty JSON object on error
        """
        try:
            config = {}
            if json_mode:
                config["response_mime_type"] = "application/json"

            response = self.client.models.generate_content(
                model=self._model_name,
                contents=prompt_parts,
                config=config if config else None,
            )

            # Log cost if token metadata available
            try:
                from src.cost_tracking import log_api_call

                usage = getattr(response, "usage_metadata", None)
                if usage:
                    log_api_call(
                        "vertex",
                        self._model_name,
                        getattr(usage, "prompt_token_count", 0),
                        getattr(usage, "candidates_token_count", 0),
                    )
            except Exception:
                pass

            return response.text
        except Exception as e:
            raise _classify_provider_error(e, "Vertex AI") from e

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Load an image file as bytes for Vertex AI multimodal prompts.

        Args:
            image_path: Path to the image file to load

        Returns:
            Dict with mime_type and data suitable for the Vertex AI API

        Raises:
            ValueError: If the file is not a valid image or MIME type cannot be determined
        """
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"Could not determine image MIME type or it's not an image: {image_path}")

        from google.genai import types

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


class MockLLMProvider(LLMProvider):
    """
    Mock implementation of LLMProvider for cost-free development and testing.
    Returns fabricated but realistic responses without making external API calls.
    """

    def __init__(self):
        """Initialize mock provider (no API keys needed)."""
        from src.mock_responses import get_mock_response

        self._get_mock_response = get_mock_response
        self._call_count = 0

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate fabricated content based on prompt context.

        Args:
            prompt_parts: List of prompt parts (text and images)
            json_mode: Whether to return JSON (always True for mock)

        Returns:
            Fabricated but realistic JSON response
        """
        self._call_count += 1

        # Use mock_responses module to generate realistic responses
        response = self._get_mock_response(prompt_parts=prompt_parts, json_mode=json_mode)

        return response

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Prepare a mock image context (no actual image loading).

        Args:
            image_path: Path to image file

        Returns:
            Mock image object (string representation)
        """
        # Return a mock image object that won't cause errors
        return f"<MockImage: {image_path}>"


class OpenAICompatibleProvider(LLMProvider):
    """
    LLM provider for any OpenAI-compatible API.
    Works with OpenAI, Anthropic, Mistral, Ollama, OpenRouter, vLLM, LiteLLM, etc.
    """

    def __init__(self, api_key: str, base_url: str, model_name: str = "gpt-4o"):
        """
        Initialize the OpenAI-compatible provider.

        Args:
            api_key: API key for authentication
            base_url: Base URL of the OpenAI-compatible API (e.g., https://api.openai.com/v1)
            model_name: Model name to use (e.g., gpt-4o, mistral-large, llama3)
        """
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self._model_name = model_name

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using an OpenAI-compatible API.

        Args:
            prompt_parts: List of prompt components (text strings and/or image dicts)
            json_mode: If True, request JSON-formatted output

        Returns:
            Generated text response, or empty JSON on error
        """
        try:
            content_parts = []
            for part in prompt_parts:
                if isinstance(part, str):
                    content_parts.append({"type": "text", "text": part})
                elif isinstance(part, dict) and part.get("type") == "image_url":
                    content_parts.append(part)
                # Skip unknown types gracefully

            messages = [{"role": "user", "content": content_parts}]
            kwargs = {"model": self._model_name, "messages": messages}
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)

            # Log cost if usage data available
            try:
                from src.cost_tracking import log_api_call

                usage = response.usage
                if usage:
                    log_api_call(
                        "openai-compatible",
                        self._model_name,
                        getattr(usage, "prompt_tokens", 0),
                        getattr(usage, "completion_tokens", 0),
                    )
            except Exception:
                pass

            return response.choices[0].message.content
        except Exception as e:
            raise _classify_provider_error(e, "OpenAI-compatible") from e

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Encode an image as a base64 data URL for OpenAI vision format.

        Args:
            image_path: Path to the image file

        Returns:
            Dict in OpenAI image_url format with base64-encoded data
        """
        import base64

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}


class AnthropicProvider(LLMProvider):
    """
    LLM provider for Anthropic's Claude models via the direct API.
    Requires an ANTHROPIC_API_KEY.
    """

    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-20250514"):
        """
        Initialize the Anthropic provider with API credentials.

        Args:
            api_key: Anthropic API key for authentication
            model_name: Name of the Claude model to use
        """
        if not _ANTHROPIC_AVAILABLE:
            raise ImportError("The Anthropic library is not installed. Run: pip install anthropic")
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)
        self._model_name = model_name

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using the Anthropic Messages API.

        Args:
            prompt_parts: List of prompt components (text strings and/or image dicts)
            json_mode: If True, prepend a system prompt requesting JSON output

        Returns:
            Generated text response from the model, or empty JSON on error
        """
        try:
            content_parts = []
            for part in prompt_parts:
                if isinstance(part, str):
                    content_parts.append({"type": "text", "text": part})
                elif isinstance(part, dict) and part.get("type") == "image":
                    content_parts.append(part)
                # Skip unknown types gracefully

            kwargs = {
                "model": self._model_name,
                "messages": [{"role": "user", "content": content_parts}],
                "max_tokens": 8192,
            }
            if json_mode:
                kwargs["system"] = "Respond only with valid JSON."

            response = self.client.messages.create(**kwargs)

            # Log cost if usage data available
            try:
                from src.cost_tracking import log_api_call

                usage = response.usage
                if usage:
                    log_api_call(
                        "anthropic",
                        self._model_name,
                        getattr(usage, "input_tokens", 0),
                        getattr(usage, "output_tokens", 0),
                    )
            except Exception:
                pass

            return response.content[0].text
        except Exception as e:
            raise _classify_provider_error(e, "Anthropic") from e

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Encode an image as base64 in Anthropic's vision format.

        Args:
            image_path: Path to the image file

        Returns:
            Dict in Anthropic image format with base64-encoded data
        """
        import base64

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": b64,
            },
        }


class VertexAnthropicProvider(LLMProvider):
    """
    LLM provider for Claude models via Google Cloud Vertex AI Model Garden.
    Uses GCP application-default credentials (no API key needed).
    """

    def __init__(self, project_id: str, location: str, model_name: str = "claude-sonnet-4@20250514"):
        """
        Initialize the Vertex AI Claude provider with GCP credentials.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., 'us-east5')
            model_name: Name of the Claude model on Vertex AI
        """
        if not _ANTHROPIC_AVAILABLE:
            raise ImportError("The Anthropic library is not installed. Run: pip install anthropic[vertex]")
        from anthropic import AnthropicVertex

        self.client = AnthropicVertex(project_id=project_id, region=location)
        self._model_name = model_name

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using Claude via Vertex AI.

        Args:
            prompt_parts: List of prompt components (text strings and/or image dicts)
            json_mode: If True, prepend a system prompt requesting JSON output

        Returns:
            Generated text response from the model, or empty JSON on error
        """
        try:
            content_parts = []
            for part in prompt_parts:
                if isinstance(part, str):
                    content_parts.append({"type": "text", "text": part})
                elif isinstance(part, dict) and part.get("type") == "image":
                    content_parts.append(part)

            kwargs = {
                "model": self._model_name,
                "messages": [{"role": "user", "content": content_parts}],
                "max_tokens": 8192,
            }
            if json_mode:
                kwargs["system"] = "Respond only with valid JSON."

            response = self.client.messages.create(**kwargs)

            # Log cost if usage data available
            try:
                from src.cost_tracking import log_api_call

                usage = response.usage
                if usage:
                    log_api_call(
                        "vertex-anthropic",
                        self._model_name,
                        getattr(usage, "input_tokens", 0),
                        getattr(usage, "output_tokens", 0),
                    )
            except Exception:
                pass

            return response.content[0].text
        except Exception as e:
            raise _classify_provider_error(e, "Vertex AI (Claude)") from e

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Encode an image as base64 in Anthropic's vision format.

        Args:
            image_path: Path to the image file

        Returns:
            Dict in Anthropic image format with base64-encoded data
        """
        import base64

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png"
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": b64,
            },
        }


# --- Provider Registry ---
# Metadata about available providers for UI display and configuration.
# default_model: the model used when user hasn't set llm.model_name.
# Update these defaults when Google/OpenAI deprecate model versions.

PROVIDER_REGISTRY = {
    "mock": {
        "label": "Mock (Development)",
        "description": "Zero-cost fabricated responses for testing",
        "category": "built-in",
    },
    "gemini": {
        "label": "Google Gemini Flash",
        "description": "Fast, cost-effective model via Gemini API",
        "category": "built-in",
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
    },
    "gemini-pro": {
        "label": "Google Gemini Pro",
        "description": "Advanced model via Gemini API",
        "category": "built-in",
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-pro",
    },
    "gemini-3-flash": {
        "label": "Google Gemini 3 Flash",
        "description": "Latest generation fast model (preview)",
        "category": "built-in",
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-3-flash-preview",
    },
    "gemini-3-pro": {
        "label": "Google Gemini 3 Pro",
        "description": "Latest generation advanced model (preview)",
        "category": "built-in",
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-3-pro-preview",
    },
    "vertex": {
        "label": "Google Vertex AI",
        "description": "Enterprise Gemini via Google Cloud",
        "category": "built-in",
        "requires_config": ["vertex_project_id", "vertex_location"],
        "default_model": "gemini-2.5-flash",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "description": "Claude Sonnet via Anthropic API",
        "category": "built-in",
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
    },
    "vertex-anthropic": {
        "label": "Vertex AI (Claude)",
        "description": "Claude via Google Cloud Vertex AI",
        "category": "built-in",
        "requires_config": ["vertex_project_id", "vertex_location"],
        "default_model": "claude-sonnet-4@20250514",
    },
    "openai": {
        "label": "OpenAI",
        "description": "GPT-4o, GPT-4, etc. via OpenAI API",
        "category": "openai-compatible",
        "env_var": "OPENAI_API_KEY",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
    },
    "openai-compatible": {
        "label": "Custom (OpenAI-Compatible)",
        "description": "Any OpenAI-compatible API (Ollama, Mistral, OpenRouter, etc.)",
        "category": "openai-compatible",
        "default_model": "default",
    },
}

# Backward-compat aliases: old provider names → current names
_PROVIDER_ALIASES = {
    # No aliases for gemini-3-flash / gemini-3-pro — they have their own registry entries
}


def _resolve_provider_name(name):
    """Resolve backward-compatible provider aliases."""
    return _PROVIDER_ALIASES.get(name, name)


def get_provider_info(config):
    """
    Return a list of provider info dicts with availability status.

    Args:
        config: Application configuration dictionary

    Returns:
        List of dicts with keys: key, label, description, available, reason
    """
    llm_config = config.get("llm", {})
    current_provider = _resolve_provider_name(llm_config.get("provider", "mock"))
    result = []
    for key, meta in PROVIDER_REGISTRY.items():
        info = {
            "key": key,
            "label": meta["label"],
            "description": meta["description"],
            "available": True,
            "reason": "",
        }

        if key == "mock":
            # Always available
            pass
        elif meta.get("env_var"):
            # Check provider-specific env var first
            env_val = os.getenv(meta["env_var"]) or ""
            # Only fall back to shared api_key if this IS the currently selected provider
            if not env_val and key == current_provider:
                env_val = llm_config.get("api_key", "")
            if not env_val:
                info["available"] = False
                info["reason"] = f"Set {meta['env_var']} or enter API key in settings"
        elif key == "vertex":
            if not _GENAI_AVAILABLE:
                info["available"] = False
                info["reason"] = "google-genai not installed"
            else:
                for cfg_key in meta.get("requires_config", []):
                    if not llm_config.get(cfg_key):
                        info["available"] = False
                        info["reason"] = f"Missing config: {cfg_key}"
                        break
        elif key == "vertex-anthropic":
            if not _ANTHROPIC_AVAILABLE:
                info["available"] = False
                info["reason"] = "anthropic package not installed"
            else:
                for cfg_key in meta.get("requires_config", []):
                    if not llm_config.get(cfg_key):
                        info["available"] = False
                        info["reason"] = f"Missing config: {cfg_key}"
                        break
        elif key == "openai-compatible":
            # Available if user has configured base_url and api_key
            if not llm_config.get("base_url") or not llm_config.get("api_key"):
                info["available"] = False
                info["reason"] = "Configure base URL and API key in settings"

        result.append(info)
    return result


# A factory function to get the correct provider based on configuration
def get_provider(config, web_mode=False):
    """
    Factory function to instantiate the correct LLM provider based on config.

    Includes cost control mechanism: prompts user for approval when using real APIs
    in development mode. Automatically falls back to MockLLMProvider if user declines.

    Args:
        config: Application configuration dictionary containing 'llm' settings with:
            - provider: One of 'mock', 'gemini', 'gemini-pro', 'vertex',
                       'openai', 'openai-compatible'
            - mode: 'development' or 'production' (affects approval gate)
            - model_name: Name of model to use (provider-specific)
            - vertex_project_id: Required for Vertex AI provider
            - vertex_location: Required for Vertex AI provider
            - api_key: API key for OpenAI/custom providers
            - base_url: Base URL for OpenAI-compatible providers
        web_mode: If True, skip interactive input() approval gate (for web UI)

    Returns:
        LLMProvider: Instance of the appropriate provider class

    Raises:
        ValueError: If provider is unsupported, missing API keys, or missing config values
        ImportError: If Vertex AI selected but google-genai not installed
    """
    provider_name = config.get("llm", {}).get("provider", "mock")
    llm_config = config.get("llm", {})

    # Resolve backward-compatible aliases (e.g., gemini-3-pro → gemini-pro)
    provider_name = _resolve_provider_name(provider_name)

    # Read default model from registry
    registry_entry = PROVIDER_REGISTRY.get(provider_name, {})
    default_model = registry_entry.get("default_model", "default")

    # User's model_name always takes priority over registry default
    model_name = llm_config.get("model_name") or default_model

    # Check if using real provider and warn user
    real_providers = [
        "gemini",
        "gemini-pro",
        "gemini-3-flash",
        "gemini-3-pro",
        "vertex",
        "anthropic",
        "vertex-anthropic",
        "openai",
        "openai-compatible",
    ]
    if provider_name in real_providers:
        mode = llm_config.get("mode", "development")
        if mode == "development" and not web_mode:
            print("\n[WARNING] Using real API - costs will be incurred!")
            print(f"   Provider: {provider_name}")
            print("   To use cost-free mock provider, set llm.provider: 'mock' in config.yaml")
            print("   Continue with real API? (yes/no): ", end="")

            # In automated environments, default to no
            try:
                response = input().strip().lower()
                if response != "yes":
                    print("\n   Switching to mock provider for cost-free development.")
                    provider_name = "mock"
            except (EOFError, KeyboardInterrupt):
                print("\n   No input received. Switching to mock provider.")
                provider_name = "mock"

    if provider_name == "mock":
        return MockLLMProvider()
    elif provider_name in ("gemini", "gemini-pro", "gemini-3-flash", "gemini-3-pro"):
        api_key = os.getenv("GEMINI_API_KEY") or llm_config.get("api_key", "")
        if not api_key:
            raise ValueError(
                "No Gemini API key found. Go to Settings > Setup Wizard to enter your API key, or set the GEMINI_API_KEY environment variable."
            )
        return GeminiProvider(
            api_key=api_key,
            model_name=model_name,
        )
    elif provider_name == "vertex":
        if not _GENAI_AVAILABLE:
            raise ImportError("The Google AI library is not installed. Run: pip install google-genai")
        project_id = llm_config.get("vertex_project_id")
        location = llm_config.get("vertex_location")
        if not project_id or not location:
            raise ValueError(
                "Vertex AI requires a Google Cloud Project ID and Region. Go to Settings to enter these, or use the Setup Wizard for step-by-step guidance."
            )
        return VertexAIProvider(
            project_id=project_id,
            location=location,
            model_name=model_name,
        )
    elif provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY") or llm_config.get("api_key", "")
        if not api_key:
            raise ValueError(
                "No Anthropic API key found. Go to Settings > Setup Wizard to enter your API key, or set the ANTHROPIC_API_KEY environment variable."
            )
        return AnthropicProvider(
            api_key=api_key,
            model_name=model_name,
        )
    elif provider_name == "vertex-anthropic":
        if not _ANTHROPIC_AVAILABLE:
            raise ImportError("The Anthropic library is not installed. Run: pip install anthropic[vertex]")
        project_id = llm_config.get("vertex_project_id")
        location = llm_config.get("vertex_location")
        if not project_id or not location:
            raise ValueError(
                "Vertex AI (Claude) requires a Google Cloud Project ID and Region. Go to Settings to enter these, or use the Setup Wizard for step-by-step guidance."
            )
        return VertexAnthropicProvider(
            project_id=project_id,
            location=location,
            model_name=model_name,
        )
    elif provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or llm_config.get("api_key", "")
        if not api_key:
            raise ValueError(
                "No OpenAI API key found. Go to Settings > Setup Wizard to enter your API key, or set the OPENAI_API_KEY environment variable."
            )
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            model_name=model_name,
        )
    elif provider_name == "openai-compatible":
        api_key = llm_config.get("api_key", "")
        base_url = llm_config.get("base_url", "")
        if not base_url:
            raise ValueError(
                "No API endpoint URL configured for your custom provider. Go to Settings and enter the Base URL (e.g., http://localhost:11434/v1 for Ollama)."
            )
        return OpenAICompatibleProvider(
            api_key=api_key or "no-key",
            base_url=base_url,
            model_name=model_name,
        )
    else:
        raise ValueError(
            f"Unsupported provider: '{provider_name}'. Go to Settings to choose a supported provider (Gemini, Anthropic, OpenAI, Vertex AI, or Mock)."
        )
