import unittest
import yaml
from src.llm_provider import get_provider


class TestModelOptimizer(unittest.TestCase):
    def test_model_optimizer_generation(self):
        """Tests that the Model Optimizer can be loaded and used for generation."""
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)

        # Override the model name to use the model optimizer
        config["llm"]["model_name"] = "model-optimizer-exp-04-09"
        config["llm"]["provider"] = "vertex"

        with self.assertRaises(Exception) as context:
            provider = get_provider(config)
            provider.generate(["Write a short story about a brave knight."])

        self.assertTrue(
            "was not found or your project does not have access to it"
            in str(context.exception)
        )


if __name__ == "__main__":
    unittest.main()
