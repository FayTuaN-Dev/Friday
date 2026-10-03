"""Transforme un texte en vecteur de sens (embedding), avec un petit modèle Ollama sur CPU."""

import numpy as np
import ollama

# Certains modèles attendent un préfixe différent pour les questions et pour les souvenirs.
PREFIXES = {
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
}


class Embedder:
    def __init__(self, model: str, client: ollama.Client) -> None:
        self.model = model
        self.client = client
        self._query_prefix, self._doc_prefix = PREFIXES.get(model.split(":")[0], ("", ""))

    def documents(self, texts: list[str]) -> np.ndarray:
        return self._embed([self._doc_prefix + t for t in texts])

    def query(self, text: str) -> np.ndarray:
        return self._embed([self._query_prefix + text])[0]

    def _embed(self, inputs: list[str]) -> np.ndarray:
        response = self.client.embed(
            model=self.model,
            input=inputs,
            keep_alive="30m",
            options={"num_gpu": 0},  # sur CPU (~40 ms) : la carte graphique reste au LLM
        )
        vectors = np.array(response.embeddings, dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
