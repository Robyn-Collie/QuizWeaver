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
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
        try:
            # The Gemini API expects a list of parts (text, images)
            generation_config = {}
            if json_mode:
                generation_config = {"response_mime_type": "application/json"}

            response = self.model.generate_content(
                prompt_parts, generation_config=generation_config
            )
            return response.text
        except Exception as e:
            print(f"An error occurred with the Gemini provider: {e}")
            return "[]"  # Return an empty JSON array on error

    def prepare_image_context(self, image_path: str) -> Any:
        return genai.upload_file(image_path)


class Gemini3ProProvider(LLMProvider):
    """
    Concrete implementation for the advanced Gemini 3 Pro model.
    Specialized for multimodal tasks and structured output.
    """

    def __init__(
        self, api_key: str, model_name: str = "gemini-2.0-flash-exp"
    ):  # Using 2.0 Flash Exp as proxy for 3 Pro Preview if needed, or actual name
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt_parts: list, json_mode: bool = False) -> str:
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
        return genai.upload_file(image_path)


class VertexAIProvider(LLMProvider):
    """
    Concrete implementation of the LLMProvider for Google Cloud Vertex AI models.
    """

    def __init__(
        self, project_id: str, location: str, model_name: str = "gemini-1.5-flash"
    ):
        if not _VERTEX_AI_AVAILABLE:
            raise ImportError("google-cloud-aiplatform is not installed or available.")

        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel(model_name)

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
            return response.text
        except Exception as e:
            print(f"An error occurred with the Vertex AI provider: {e}")
            return "{}"

    def prepare_image_context(self, image_path: str) -> Any:
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


# A factory function to get the correct provider based on configuration
def get_provider(config):
    """
    Factory function to instantiate the correct LLM provider based on config.
    """
    provider_name = config.get("llm", {}).get("provider", "mock")
    llm_config = config.get("llm", {})

    # Check if using real provider and warn user
    if provider_name in ["gemini", "gemini-3-pro", "vertex"]:
        mode = llm_config.get("mode", "development")
        if mode == "development":
            print("\n⚠️  WARNING: Using real API - costs will be incurred!")
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
        return GeminiProvider(api_key=api_key)
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
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
