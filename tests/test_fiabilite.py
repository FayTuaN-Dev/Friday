"""Fiabilité (F1) : rechargement d'Ollama si sa vitesse s'effondre, sauvegarde quotidienne de
data/, page Diagnostic."""

import json
import sqlite3
import zipfile
from datetime import datetime, timedelta
from types import SimpleNamespace

from friday.app.backup import DailyBackup, backup, last_backup
from friday.app.diagnostic import BAD, OK, WARN, collect, gpu
from friday.brain.speed_watch import SpeedWatch


def chunk(tokens, seconds):
    return SimpleNamespace(eval_count=tokens, eval_duration=int(seconds * 1e9))


def test_the_model_is_reloaded_when_speed_collapses_twice():
    reloads, clock = [], [0.0]
    watch = SpeedWatch(lambda: reloads.append(1), clock=lambda: clock[0], background=False)
    for _ in range(3):
        watch.record(chunk(400, 10))  # 40 jetons/s : la normale
    watch.record(chunk(5, 1))  # trop court : ne compte pas
    watch.record(chunk(100, 10))  # 10 jetons/s : lent (1/2)
    assert reloads == [] and watch.strikes == 1
    watch.record(chunk(400, 10))  # redevenu normal : on repart de zéro
    watch.record(chunk(100, 10))
    watch.record(chunk(100, 10))
    assert reloads == [1] and watch.normal > 35
    watch.record(chunk(100, 10))
    watch.record(chunk(100, 10))
    assert reloads == [1]  # pas deux rechargements en 10 min
    clock[0] = 700
    watch.record(chunk(100, 10))
    watch.record(chunk(100, 10))
    assert reloads == [1, 1]


def fill(data):
    db = sqlite3.connect(data / "trading.db")
    db.execute("CREATE TABLE trades (id INTEGER, pair TEXT)")
    db.execute("INSERT INTO trades VALUES (1, 'XAUUSD')")
    db.commit()
    db.close()
    (data / "trading_plans.json").write_text(json.dumps([{"nom": "Cassure"}]), "utf-8")
    for skipped in ("cache", "bibliotheque", "models"):
        (data / skipped).mkdir()
        (data / skipped / "gros.bin").write_bytes(b"x" * 100)
    (data / "library.db").write_bytes(b"index")
    (data / "google_token.json").write_text('{"secret": 1}', "utf-8")  # jamais copié


def test_backup_keeps_what_matters_and_only_seven(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    fill(data)
    usb = tmp_path / "usb"
    archive = backup(data, copy_to=usb, now=datetime(2026, 9, 1, 8, 0))  # date fixe
    names = set(zipfile.ZipFile(archive).namelist())
    assert names == {"trading.db", "trading_plans.json"}  # ni caches, ni modèles, ni PDF
    restored = tmp_path / "restored.db"
    restored.write_bytes(zipfile.ZipFile(archive).read("trading.db"))
    db = sqlite3.connect(restored)
    assert db.execute("SELECT pair FROM trades").fetchall() == [("XAUUSD",)]
    db.close()
    assert (usb / archive.name).is_file()
    start = datetime(2026, 10, 1, 9, 0)
    for day in range(9):
        backup(data, now=start + timedelta(days=day))
    assert len(list((data / "sauvegardes").glob("*.zip"))) == 7
    assert last_backup(data).name == "friday-2026-10-09-0900.zip"


def test_daily_backup_is_due_once_a_day(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    fill(data)
    daily = DailyBackup(data)
    assert daily.due()
    assert daily.run_now() is not None and not daily.due()
    assert daily.due(datetime.now() + timedelta(hours=25))
    broken = DailyBackup(tmp_path / "absent")
    assert broken.run_now() is not None  # dossier vide : archive vide, pas d'erreur


SETTINGS = SimpleNamespace(ollama_model="qwen3:8b", embed_model="embeddinggemma",
                           tts_voice="fr_FR-siwis-medium", mic_device=None, stt_model="large-v3",
                           backup_dir="")  # fmt: skip


class Client:
    def __init__(self, models=("qwen3:8b", "embeddinggemma:latest"), share=1.0, down=False):
        self.models, self.share, self.down = models, share, down

    def list(self):
        if self.down:
            raise ConnectionError("refusé")
        return SimpleNamespace(models=[SimpleNamespace(model=m) for m in self.models])

    def ps(self):
        return SimpleNamespace(
            models=[
                SimpleNamespace(
                    model="qwen3:8b", name="qwen3:8b", size=100, size_vram=100 * self.share
                )
            ]
        )


def nvidia(*args, **kwargs):
    return SimpleNamespace(stdout="NVIDIA GeForce RTX 3070, 6655, 8192, 37\n")


def test_diagnostic_says_what_is_wrong(tmp_path):
    watch = SpeedWatch(lambda: None, background=False)
    watch.record(chunk(400, 10))
    components = SimpleNamespace(brain=SimpleNamespace(client=Client(), speed=watch),
                                 speaker=object(), recorder=object(), stt=object())  # fmt: skip
    lines = {topic: (state, detail) for topic, state, detail in
             collect(components, SETTINGS, tmp_path, nvidia)}  # fmt: skip
    assert lines["Ollama"][0] == OK and lines["Modèle de la mémoire"][0] == OK
    assert lines["Chargement"] == (OK, "100% du modèle dans la carte graphique")
    assert lines["Vitesse"][0] == OK and "40 jetons/s" in lines["Vitesse"][1]
    assert lines["Carte graphique"] == (OK, "NVIDIA GeForce RTX 3070 : 6655 / 8192 Mo utilisés, "
                                            "37 °C")  # fmt: skip
    assert lines["Sauvegarde"][0] == WARN
    components.brain.client = Client(models=("qwen3:8b",), share=0.6)
    lines = {t: (s, d) for t, s, d in collect(components, SETTINGS, tmp_path, nvidia)}
    assert (
        lines["Modèle de la mémoire"][0] == BAD
        and "ollama pull" in lines["Modèle de la mémoire"][1]
    )
    assert lines["Chargement"][0] == WARN
    components.brain.client = Client(down=True)
    assert collect(components, SETTINGS, tmp_path, nvidia)[0][1] == BAD

    def missing(*args, **kwargs):
        raise OSError("nvidia-smi introuvable")

    assert gpu(missing)[0][1] == WARN


def test_diagnostic_page_and_its_buttons(tmp_path):
    from PySide6.QtWidgets import QApplication

    from friday.ui.desktop.settings.diagnostic_page import DiagnosticPage

    QApplication.instance() or QApplication([])
    data = tmp_path / "data"
    data.mkdir()
    fill(data)
    components = SimpleNamespace(brain=None, backup=DailyBackup(data))
    page = DiagnosticPage(SimpleNamespace(components=components), SETTINGS, data)
    assert page.grid.count() > 0
    page._backup()
    assert page.message.text().startswith("Sauvegarde faite : friday-")
    page._reload()
    assert "démarre encore" in page.message.text()
