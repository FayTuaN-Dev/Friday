from jarvis.core.config import load_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr("jarvis.core.config.load_dotenv", lambda *a, **k: None)
    assert load_settings().ollama_model == "qwen3:8b"


def test_env_override(monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "opus")
    assert load_settings().claude_model == "opus"
