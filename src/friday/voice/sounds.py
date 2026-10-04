"""Petits sons synthétisés (pas de fichier à fournir)."""

import numpy as np


def chime(sample_rate: int, notes: tuple[float, ...] = (880.0, 1318.5)) -> np.ndarray:
    """Carillon doux à deux notes, joué avant un rappel."""
    parts = []
    for frequency in notes:
        t = np.arange(int(sample_rate * 0.22)) / sample_rate
        envelope = np.exp(-t * 9)  # attaque nette, extinction douce
        tone = np.sin(2 * np.pi * frequency * t) + 0.3 * np.sin(4 * np.pi * frequency * t)
        parts.append(0.25 * envelope * tone)
    parts.append(np.zeros(int(sample_rate * 0.15)))  # petit silence avant la voix
    return np.concatenate(parts).astype(np.float32)
