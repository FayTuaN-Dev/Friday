"""L'état du Pi pour la carte « Pi » du PC : /proc et /sys lus sans rien d'autre."""

from friday.server.machine import Machine, memory, temperature, uptime


def test_reads_temperature_memory_and_uptime(tmp_path):
    (tmp_path / "temp").write_text("52312\n")
    (tmp_path / "meminfo").write_text("MemTotal:  8000000 kB\nMemFree: 1 kB\n"
                                      "MemAvailable:  6000000 kB\n")  # fmt: skip
    (tmp_path / "uptime").write_text("3600.42 7000.1\n")
    assert temperature(tmp_path / "temp") == 52.3
    assert memory(tmp_path / "meminfo") == (1.91, 7.63)
    assert uptime(tmp_path / "uptime") == 3600


def test_missing_values_are_left_out(tmp_path):
    assert temperature(tmp_path / "rien") is None and memory(tmp_path / "rien") is None
    machine = Machine(clock=lambda: 1000.0)
    assert "last_message" not in machine.status()
    machine.heard()
    assert machine.status()["last_message"] == 1000.0
