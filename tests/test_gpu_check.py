from types import SimpleNamespace

from friday.app.gpu_check import gpu_share, warn_if_spilling


def client(size, vram):
    loaded = SimpleNamespace(model="qwen3:8b", name="qwen3:8b", size=size, size_vram=vram)
    return SimpleNamespace(ps=lambda: SimpleNamespace(models=[loaded]))


def test_spilling_model_is_reported_with_the_fix():
    assert warn_if_spilling(client(100, 100), "qwen3:8b", 16384) is None
    message = warn_if_spilling(client(100, 80), "qwen3:8b", 16384)
    assert "80%" in message and "OLLAMA_KV_CACHE_TYPE=q8_0" in message


def test_unknown_state_says_nothing():
    def broken():
        raise ConnectionError("Ollama absent")

    assert gpu_share(SimpleNamespace(ps=broken), "qwen3:8b") is None
    assert warn_if_spilling(client(100, 50), "autre:modele", 8192) is None
