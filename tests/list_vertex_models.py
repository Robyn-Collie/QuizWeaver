import google.auth
from google.auth.transport.requests import Request
import requests
import os
import yaml


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def list_publisher_models():
    try:
        config = load_config()
        project_id = config.get("llm", {}).get("vertex_project_id")
        location = config.get("llm", {}).get("vertex_location")

        if not project_id or not location:
            print("Project ID or Location missing in config")
            return

        print(f"Checking publisher models for project: {project_id} in {location}...")

        credentials, _ = google.auth.default()
        credentials.refresh(Request())

        token = credentials.token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # API endpoint to list publisher models
        # Try endpoint without location in path (but on regional domain)
        url = (
            f"https://{location}-aiplatform.googleapis.com/v1/publishers/google/models"
        )

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"Found {len(models)} models. Showing Gemini models:")
            found_any = False
            for m in models:
                model_id = m["name"].split("/")[-1]
                if "gemini" in model_id.lower():
                    print(f" - {model_id}")
                    found_any = True

            if not found_any:
                print("No Gemini models found in the list.")
                # Print first few others to verify
                print(
                    "Sample of other models:",
                    [m["name"].split("/")[-1] for m in models[:3]],
                )

        else:
            print(f"Error listing models: {response.status_code} {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    list_publisher_models()
