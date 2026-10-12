import importlib


def test_provider_package_is_importable() -> None:
    module = importlib.import_module("football_intel.agent.providers.anthropic")

    assert module.__name__ == "football_intel.agent.providers.anthropic"
