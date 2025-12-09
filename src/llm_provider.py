from abc import ABC, abstractmethod
import google.generativeai as genai
import os

class LLMProvider(ABC):
    """
    Abstract base class for a generic LLM provider.
    This defines the interface that all concrete providers must implement.
    """
    @abstractmethod
    def generate(self, prompt_parts):
        """
        Generates content based on a list of prompt parts (text and images).

        Args:
            prompt_parts (list): A list containing strings and/or image objects.

        Returns:
            str: The generated text from the language model.
        """
        pass

class GeminiProvider(LLMProvider):
    """
    Concrete implementation of the LLMProvider for Google's Gemini models.
    """
    def __init__(self, api_key, model_name='gemini-1.5-flash'):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate(self, prompt_parts):
        try:
            # The Gemini API expects a list of parts (text, images)
            response = self.model.generate_content(prompt_parts)
            return response.text
        except Exception as e:
            print(f"An error occurred with the Gemini provider: {e}")
            return "[]" # Return an empty JSON array on error

# A factory function to get the correct provider based on configuration
def get_provider(config):
    """
    Factory function to instantiate the correct LLM provider based on config.
    """
    provider_name = config.get('llm', {}).get('provider', 'gemini')
    
    if provider_name == 'gemini':
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment.")
        return GeminiProvider(api_key=api_key)
    # Add other providers here in the future
    # elif provider_name == 'openai':
    #     api_key = os.getenv("OPENAI_API_KEY")
    #     return OpenAIProvider(api_key=api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
