# Le mot d'activation « Friday » (une seule fois, gratuit)

Avec ce petit modèle, Friday écoute « Friday » en continu sur le processeur, et Whisper ne
transcrit plus que les phrases qui commencent par son nom (ou une relance juste après une
réponse). Résultat : beaucoup moins de faux réveils (télé, conversations), et la carte
graphique au repos. L'utilisation est **100 % locale** ; seul l'entraînement, une fois, se
fait sur Google Colab (gratuit, avec des voix de synthèse : aucune donnée personnelle).

Sans ce fichier, Friday écoute comme avant (Whisper sur toutes les phrases).

## Étapes (environ 1 h, surtout de l'attente)

1. Ouvre le notebook officiel d'openWakeWord :
   <https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing>
   (connexion avec un compte Google, gratuite).
2. Dans le champ du mot à entraîner (*target word / phrase*), écris : `friday`.
   Le notebook fait prononcer ce mot par des centaines de voix de synthèse. Si à l'écoute
   de l'exemple la prononciation sonne faux, essaie `fry day`.
3. Lance tout : menu **Exécution → Tout exécuter**. Laisse l'onglet ouvert jusqu'à la fin
   (moins d'une heure).
4. À la fin, télécharge le fichier du modèle au format **`.onnx`** (pas le `.tflite`).
5. Renomme-le **`friday.onnx`** et dépose-le dans le dossier `data/models` de Friday.
6. Relance Friday. Dans **Réglages → Diagnostic**, la ligne « Mot d'activation » doit être
   ✅ « modèle « Friday » installé ».

## Régler la sensibilité

**Réglages → Écoute → Exigence du mot d'activation** (0,5 par défaut) :

- Friday se réveille toute seule (télé, conversation) : monte à 0,6 ou 0,7.
- Elle ne t'entend pas bien : descends à 0,4 ou 0,3.

Pour revenir à l'écoute d'avant, il suffit de retirer `data/models/friday.onnx`.
