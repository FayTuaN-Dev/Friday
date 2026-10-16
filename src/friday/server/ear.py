"""L'oreille du Friday du Pi (R3) : le téléphone envoie l'enregistrement (WebM/Opus, bouton
maintenu), Whisper le transcrit sur le processeur du Pi.

Constaté sur le Pi 5, une phrase de 4 s : Whisper « base » 2,7 s, « small » 8 s, tous deux
sans faute. Et le décodage de faster-whisper (decode_audio) plante avec PyAV 19
(« metadata_errors ») : on décode donc nous-mêmes."""

import io
import logging

import numpy as np

from friday.voice.rate import WHISPER_RATE

log = logging.getLogger(__name__)
MAX_AUDIO = 5_000_000  # octets : environ 20 minutes d'Opus, bien plus qu'une phrase


def decode(data: bytes) -> np.ndarray:
    """N'importe quel enregistrement (WebM, Ogg, WAV…) → mono 16 kHz, float32 entre -1 et 1."""
    import av

    out = []
    with av.open(io.BytesIO(data)) as box:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=WHISPER_RATE)
        for frame in box.decode(audio=0):
            out += [f.to_ndarray() for f in resampler.resample(frame)]
        out += [f.to_ndarray() for f in resampler.resample(None)]
    if not out:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(out, axis=1).ravel().astype(np.float32) / 32768


class Ear:
    def __init__(self, model: str, models_dir, hotword: str = "Friday") -> None:
        from friday.voice.stt import WhisperSTT

        self.stt = WhisperSTT(model, "cpu", models_dir, hotword)

    def hear(self, data: bytes) -> str:
        """Le texte entendu ("" : rien de compréhensible, ou un son illisible)."""
        try:
            return self.stt.transcribe(decode(data))
        except Exception as error:  # fichier abîmé, format inconnu : on le dit, sans planter
            log.warning("Enregistrement illisible : %s", error)
            return ""
