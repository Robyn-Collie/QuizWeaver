from abc import ABC, abstractmethod
import google.generativeai as genai
import os


class LLMProvider(ABC):
    """
    Abstract base class for a generic LLM provider.
    This defines the interface that all concrete providers must implement.
    """

    @abstractmethod
    def generate(self, prompt_parts, json_mode=False):
        """
        Generates content based on a list of prompt parts (text and images).

        Args:
            prompt_parts (list): A list containing strings and/or image objects.
            json_mode (bool): Whether to force JSON output.

        Returns:
            str: The generated text from the language model.
        """
        pass


class GeminiProvider(LLMProvider):
    """
    Concrete implementation of the LLMProvider for Google's Gemini models.
    """

    def __init__(self, api_key, model_name="gemini-1.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt_parts, json_mode=False):
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


class Gemini3ProProvider(LLMProvider):
    """
    Concrete implementation for the advanced Gemini 3 Pro model.
    Specialized for multimodal tasks and structured output.
    """

    def __init__(
        self, api_key, model_name="gemini-2.0-flash-exp"
    ):  # Using 2.0 Flash Exp as proxy for 3 Pro Preview if needed, or actual name
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt_parts, json_mode=False):
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


# A factory function to get the correct provider based on configuration
def get_provider(config):
    """
    Factory function to instantiate the correct LLM provider based on config.
    """
    provider_name = config.get("llm", {}).get("provider", "gemini")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment.")

    if provider_name == "gemini":
        return GeminiProvider(api_key=api_key)
    elif provider_name == "gemini-3-pro":
        return Gemini3ProProvider(
            api_key=api_key, model_name="gemini-2.0-flash-exp"
        )  # Update model name when available
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
