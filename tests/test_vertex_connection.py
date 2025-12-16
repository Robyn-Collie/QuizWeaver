import sys
import os
import yaml

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm_provider import get_provider


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def test_vertex_connection():
    print("--- Starting Vertex AI Connection Test ---")

    try:
        config = load_config()
        llm_config = config.get("llm", {})
        print(
            f"Loaded LLM Config: provider={llm_config.get('provider')}, project={llm_config.get('vertex_project_id')}, location={llm_config.get('vertex_location')}"
        )

        # Ensure we are testing Vertex
        if llm_config.get("provider") != "vertex":
            print(
                "NOTE: Configured provider is not 'vertex'. This test is specifically for Vertex AI."
            )
            # We can force it for the test if we had credentials, but we rely on config.

        print("\nInitializing Provider...")
        provider = get_provider(config)
        print(f"Provider initialized: {type(provider).__name__}")

        if type(provider).__name__ == "VertexAIProvider":
            print("\nSending test generation request...")
            response = provider.generate(
                [
                    "Hello! Please respond with 'Connection Successful' if you receive this."
                ]
            )
            print("\n--- Response from Vertex AI ---")
            print(response)
            print("-------------------------------")
        else:
            print("Skipping Vertex-specific test because another provider is active.")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_vertex_connection()
