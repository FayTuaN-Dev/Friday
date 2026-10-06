import pytest

from friday.voice import devices

MIC = "Microphone (2- Auna Mic CM900)"


def device(name, inputs, outputs, api):
    return {"name": name, "max_input_channels": inputs, "max_output_channels": outputs,
            "hostapi": api}  # fmt: skip


DEVICES = [device(MIC, 1, 0, 0), device("Speakers (GameDAC Game)", 0, 6, 0),
           device(MIC, 1, 0, 1), device(MIC, 1, 0, 2)]  # fmt: skip


@pytest.fixture(autouse=True)
def fake_sounddevice(monkeypatch):
    monkeypatch.setattr(devices.sd, "query_devices", lambda: DEVICES)
    monkeypatch.setattr(devices.sd, "query_hostapis", lambda i: {"name": f"api{i}"})
    monkeypatch.setattr(devices, "default_hostapi", lambda: 2)


def test_same_microphone_listed_three_times_gives_one_device():
    assert devices.resolve_device(MIC, "input") == 3  # API par défaut
    assert devices.resolve_device("auna", "input") == 3  # morceau de nom


def test_numbers_default_and_unknown():
    assert devices.resolve_device(None, "input") is None
    assert devices.resolve_device("", "output") is None
    assert devices.resolve_device("4", "input") == 4
    assert devices.resolve_device("GameDAC", "output") == 1  # seule sortie : autre API acceptée
    with pytest.raises(ValueError, match="introuvable"):
        devices.resolve_device("Inexistant", "input")
