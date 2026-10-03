import os

# Les tests de l'interface tournent sans écran (CI)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
