from abc import ABC, abstractmethod
import google.generativeai as genai
import os
import mimetypes
from PIL import Image as PILImage
import io
from typing import Any

# Try to import vertexai only if available (will be installed from requirements.txt)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part

    _VERTEX_AI_AVAILABLE = True
except ImportError:
    _VERTEX_AI_AVAILABLE = False


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
    Concrete implementation of the LLMProvider for Google's Gemini models.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        """
        Initialize the Gemini provider with API credentials.

        Args:
            api_key: Google Gemini API key for authentication
            model_name: Name of the Gemini model to use (default: gemini-1.5-flash)
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self._model_name = model_name

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using the Gemini API.

        Args:
            prompt_parts: List of prompt components (text strings and/or image objects)
            json_mode: If True, configures the model to return JSON-formatted output

        Returns:
            Generated text response from the model, or empty JSON array on error

        Raises:
            Exception: Caught internally and returns "[]" to prevent crashes
        """
        try:
            # The Gemini API expects a list of parts (text, images)
            generation_config = {}
            if json_mode:
                generation_config = {"response_mime_type": "application/json"}

            response = self.model.generate_content(
                prompt_parts, generation_config=generation_config
            )

            # Log cost if token metadata available
            try:
                from src.cost_tracking import log_api_call
                usage = getattr(response, 'usage_metadata', None)
                if usage:
                    log_api_call(
                        "gemini", self._model_name,
                        getattr(usage, 'prompt_token_count', 0),
                        getattr(usage, 'candidates_token_count', 0),
                    )
            except Exception:
                pass

            return response.text
        except Exception as e:
            print(f"An error occurred with the Gemini provider: {e}")
            return "[]"  # Return an empty JSON array on error

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Upload an image file to Gemini API for use in multimodal prompts.

        Args:
            image_path: Path to the image file to upload

        Returns:
            Gemini file object that can be passed to generate()
        """
        return genai.upload_file(image_path)


class Gemini3ProProvider(LLMProvider):
    """
    Concrete implementation for the advanced Gemini 3 Pro model.
    Specialized for multimodal tasks and structured output.
    """

    def __init__(
        self, api_key: str, model_name: str = "gemini-2.0-flash-exp"
    ):  # Using 2.0 Flash Exp as proxy for 3 Pro Preview if needed, or actual name
        """
        Initialize the Gemini 3 Pro provider with API credentials.

        Args:
            api_key: Google Gemini API key for authentication
            model_name: Name of the advanced Gemini model (default: gemini-2.0-flash-exp)
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using the advanced Gemini 3 Pro API.

        Args:
            prompt_parts: List of prompt components (text strings and/or image objects)
            json_mode: If True, configures the model to return JSON-formatted output

        Returns:
            Generated text response from the model, or empty JSON object on error

        Raises:
            Exception: Caught internally and returns "{}" to prevent crashes
        """
        try:
            generation_config = {}
            if json_mode:
                generation_config = {"response_mime_type": "application/json"}

            # Gemini 3 Pro specific configurations could go here (e.g., thinking_level)
            # For now, we stick to the standard generate_content interface which is compatible
            response = self.model.generate_content(
                prompt_parts, generation_config=generation_config
            )
            return response.text
        except Exception as e:
            print(f"An error occurred with the Gemini 3 Pro provider: {e}")
            return "{}"

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Upload an image file to Gemini API for use in multimodal prompts.

        Args:
            image_path: Path to the image file to upload

        Returns:
            Gemini file object that can be passed to generate()
        """
        return genai.upload_file(image_path)


class VertexAIProvider(LLMProvider):
    """
    Concrete implementation of the LLMProvider for Google Cloud Vertex AI models.
    """

    def __init__(
        self, project_id: str, location: str, model_name: str = "gemini-1.5-flash"
    ):
        """
        Initialize the Vertex AI provider with Google Cloud credentials.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region (e.g., 'us-central1')
            model_name: Name of the Vertex AI model to use (default: gemini-1.5-flash)

        Raises:
            ImportError: If google-cloud-aiplatform is not installed
        """
        if not _VERTEX_AI_AVAILABLE:
            raise ImportError("google-cloud-aiplatform is not installed or available.")

        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel(model_name)
        self._model_name = model_name

    def _convert_to_vertex_part(self, item: Any) -> Any:
        if isinstance(item, PILImage.Image):
            # Convert PIL Image to bytes and then to Vertex AI Part
            byte_arr = io.BytesIO()
            item.save(byte_arr, format="PNG")
            byte_arr.seek(0)
            return Part.from_data(byte_arr.getvalue(), mime_type="image/png")
        elif isinstance(item, str):
            return item
        # Assume any other type is already a VertexAI Part/Image or compatible
        return item

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        """
        Generate content using the Vertex AI API.

        Args:
            prompt_parts: List of prompt components (text strings and/or image objects)
            json_mode: If True, configures the model to return JSON-formatted output

        Returns:
            Generated text response from the model, or empty JSON object on error

        Raises:
            Exception: Caught internally and returns "{}" to prevent crashes
        """
        try:
            generation_config = {}
            if json_mode:
                generation_config = {"response_mime_type": "application/json"}

            # Convert prompt_parts to Vertex AI compatible format
            vertex_prompt_parts = [
                self._convert_to_vertex_part(p) for p in prompt_parts
            ]

            response = self.model.generate_content(
                vertex_prompt_parts, generation_config=generation_config
            )

            # Log cost if token metadata available
            try:
                from src.cost_tracking import log_api_call
                usage = getattr(response, 'usage_metadata', None)
                if usage:
                    log_api_call(
                        "vertex", self._model_name,
                        getattr(usage, 'prompt_token_count', 0),
                        getattr(usage, 'candidates_token_count', 0),
                    )
            except Exception:
                pass

            return response.text
        except Exception as e:
            print(f"An error occurred with the Vertex AI provider: {e}")
            return "{}"

    def prepare_image_context(self, image_path: str) -> Any:
        """
        Load an image file and convert it to a Vertex AI Part object.

        Args:
            image_path: Path to the image file to load

        Returns:
            Vertex AI Part object containing the image data

        Raises:
            ValueError: If the file is not a valid image or MIME type cannot be determined
        """
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(
                f"Could not determine image MIME type or it's not an image: {image_path}"
            )

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        return Part.from_data(image_bytes, mime_type=mime_type)


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
        response = self._get_mock_response(
            prompt_parts=prompt_parts,
            json_mode=json_mode
        )

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
                        "openai-compatible", self._model_name,
                        getattr(usage, 'prompt_tokens', 0),
                        getattr(usage, 'completion_tokens', 0),
                    )
            except Exception:
                pass

            return response.choices[0].message.content
        except Exception as e:
            print(f"An error occurred with the OpenAI-compatible provider: {e}")
            return "[]"

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
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{b64}"}
        }


# --- Provider Registry ---
# Metadata about available providers for UI display and configuration

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
    },
    "gemini-3-pro": {
        "label": "Google Gemini Pro",
        "description": "Advanced multimodal model via Gemini API",
        "category": "built-in",
        "env_var": "GEMINI_API_KEY",
    },
    "vertex": {
        "label": "Google Vertex AI",
        "description": "Enterprise Gemini via Google Cloud",
        "category": "built-in",
        "requires_config": ["vertex_project_id", "vertex_location"],
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
    },
}


def get_provider_info(config):
    """
    Return a list of provider info dicts with availability status.

    Args:
        config: Application configuration dictionary

    Returns:
        List of dicts with keys: key, label, description, available, reason
    """
    llm_config = config.get("llm", {})
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
            env_val = os.getenv(meta["env_var"]) or llm_config.get("api_key", "")
            if not env_val:
                info["available"] = False
                info["reason"] = f"Set {meta['env_var']} or enter API key in settings"
        elif key == "vertex":
            if not _VERTEX_AI_AVAILABLE:
                info["available"] = False
                info["reason"] = "google-cloud-aiplatform not installed"
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
            - provider: One of 'mock', 'gemini', 'gemini-3-pro', 'vertex',
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
        ImportError: If Vertex AI selected but google-cloud-aiplatform not installed
    """
    provider_name = config.get("llm", {}).get("provider", "mock")
    llm_config = config.get("llm", {})

    # Check if using real provider and warn user
    real_providers = ["gemini", "gemini-3-pro", "vertex", "openai", "openai-compatible"]
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
    elif provider_name == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set in the environment for Gemini provider."
            )
        return GeminiProvider(
            api_key=api_key,
            model_name=llm_config.get("model_name", "gemini-1.5-flash"),
        )
    elif provider_name == "gemini-3-pro":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set in the environment for Gemini 3 Pro provider."
            )
        return Gemini3ProProvider(
            api_key=api_key,
            model_name=llm_config.get("model_name", "gemini-2.0-flash-exp"),
        )
    elif provider_name == "vertex":
        if not _VERTEX_AI_AVAILABLE:
            raise ImportError(
                "Vertex AI provider selected but google-cloud-aiplatform is not installed."
            )
        project_id = llm_config.get("vertex_project_id")
        location = llm_config.get("vertex_location")
        if not project_id or not location:
            raise ValueError(
                "Vertex AI project_id and location must be specified in config.yaml for Vertex provider."
            )
        return VertexAIProvider(
            project_id=project_id,
            location=location,
            model_name=llm_config.get("model_name", "gemini-1.5-flash"),
        )
    elif provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or llm_config.get("api_key", "")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set in the environment and no api_key in config for OpenAI provider."
            )
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            model_name=llm_config.get("model_name", "gpt-4o"),
        )
    elif provider_name == "openai-compatible":
        api_key = llm_config.get("api_key", "")
        base_url = llm_config.get("base_url", "")
        if not base_url:
            raise ValueError(
                "base_url must be set in config.yaml llm section for openai-compatible provider."
            )
        return OpenAICompatibleProvider(
            api_key=api_key or "no-key",
            base_url=base_url,
            model_name=llm_config.get("model_name", "default"),
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
