# 🤖 Jarvis — Roadmap

Assistant personnel vocal de bureau : on lui parle, il répond à voix haute et affiche le chat, des images et des résultats dans des pop-ups.

## Choix techniques

| Brique | Choix | Remarque |
|---|---|---|
| Langage | Python 3.12 (via `uv`) | 3.12 plutôt que 3.14 : meilleure compatibilité des libs audio/IA |
| Cerveau | Ollama `qwen3:8b` (local) | Supporte l'appel d'outils |
| Tâches complexes / code | Claude Code (`sonnet`, modèle configurable) | Délégué par Jarvis comme un outil |
| Transcription (STT) | `faster-whisper` large-v3-turbo (local, GPU) | ~0,5 s par phrase ; `small` en secours si la VRAM manque |
| Voix (TTS) | Piper `fr_FR-siwis-medium` (local) | Option cloud plus tard si besoin |
| Interface | PySide6 (Qt) | |
| Matériel | RTX 3070 (8 Go VRAM) | qwen3:8b ≈ 5,2 Go : il reste ~2,5 Go pour Whisper |

**Principe :** tout en local par défaut, avec le cloud uniquement pour les tâches confiées à Claude Code.

---

## Fonctionnalités

### 1. 🎙️ Écouter
- [x] Push-to-talk (touche maintenue, configurable)
- [x] Détection de fin de parole (VAD — Silero, en continu)
- [x] Transcription (`faster-whisper` large-v3-turbo sur GPU)
- [x] Mot d'activation « Jarvis » (repéré par Whisper : « Jarvis, … » d'une traite)
- [x] Interruption pendant qu'il parle (« Jarvis, … » ou « stop »)

### 2. 🧠 Réfléchir
- [x] Discussion avec Ollama (réponse en streaming)
- [x] Personnalité Jarvis (prompt système)
- [x] Mémoire de la conversation en cours
- [ ] Mémoire long terme (SQLite + embeddings)
- [x] Appel d'outils (tool calling)
- [ ] Délégation à Claude Code pour le code et les tâches complexes

### 3. 🔊 Parler
- [x] Synthèse vocale Piper
- [x] Lecture phrase par phrase (latence réduite)
- [ ] Voix synchronisée avec le texte du chat

### 4. 🖥️ Application de bureau
- [x] Fenêtre de chat (historique, streaming, saisie clavier)
- [x] Indicateur d'état (veille / écoute / réfléchit / parle) avec animation audio
- [x] Pop-ups de contenu : images, articles, résultats (code : plus tard)
- [ ] Icône dans la zone de notification
- [ ] Raccourci clavier global
- [ ] Écran de réglages (voix, micro, modèles)

### 5. 🛠️ Outils
**Information**
- [x] Recherche web + résumé
- [x] Lecture/résumé d'une page web
- [x] Recherche d'images → pop-up
- [ ] Météo, actualités, date/heure — via la recherche web pour l'instant ; un outil météo dédié serait plus fiable

**Productivité**
- [ ] Minuteurs, alarmes, rappels
- [ ] Notes et to-do
- [ ] Agenda et mails (Google)
- [ ] Calculs et conversions

**Contrôle du PC**
- [ ] Ouvrir/fermer applications et sites
- [ ] Volume, musique (Spotify)
- [ ] Recherche/lecture/résumé de fichiers
- [ ] Presse-papier
- [ ] Capture d'écran + analyse

**Bonus (plus tard)**
- [ ] Domotique (Home Assistant)
- [ ] Webcam / vision
- [ ] Routines (« Bonjour Jarvis » → météo + agenda + news)

### 6. ⚙️ Fondations
- [x] Architecture modulaire (outils = plugins), voir docs/ARCHITECTURE.md
- [x] Config `.env` + fichier de réglages
- [x] Logs (gestion d'erreurs : au fil des phases)
- [ ] Confirmation avant les actions sensibles
- [ ] Démarrage avec Windows + `.exe` (PyInstaller)

---

## Plan d'action

| # | Phase | Livrable | Statut |
|---|---|---|---|
| 0 | Mise en place : `uv`, Python 3.12, git, structure, `.env` | Projet prêt | ✅ |
| 1 | Cerveau texte : chat Ollama en terminal, historique, personnalité | On lui parle au clavier | ✅ |
| 2 | Voix de sortie : Piper, phrase par phrase | Il répond à voix haute | ✅ |
| 3 | Voix d'entrée : push-to-talk + Whisper | 1re conversation 100 % vocale | ✅ |
| 4 | Interface : fenêtre chat + indicateur d'état | Jarvis a un visage | ✅ |
| 5 | Premiers outils : recherche web + pop-ups images/textes | Il cherche et montre | ✅ |
| 6 | Mains libres : mot d'activation + interruption | Expérience naturelle | ✅ |
| 7 | Mémoire long terme | Il se souvient de toi | ⬜ |
| 8 | Outils perso + délégation Claude Code | Assistant du quotidien | ⬜ |
| 9 | Finitions : tray, démarrage auto, `.exe` | Produit fini | ⬜ |
