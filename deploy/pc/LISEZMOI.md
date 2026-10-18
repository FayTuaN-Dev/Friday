# Le PC, allumé et éteint par le Pi (R4), qui lui prête sa carte graphique (R5)

Une seule fois, **en administrateur** (clic droit sur PowerShell → « Exécuter en tant
qu'administrateur ») :

```powershell
cd C:\Users\Admin\Documents\Dev\Faytuan-Dev_Perso\Friday
powershell -ExecutionPolicy Bypass -File deploy\pc\installer.ps1
```

Le script :
1. ouvre le pare-feu à **Tailscale seulement** : Ollama (11434) et l'agent du PC (8766) ;
2. lance **Ollama au démarrage de Windows**, avant toute session (tâche « Friday - Ollama ») ;
   l'appli d'Ollama ne se lance plus avec la session (gardée dans `%LOCALAPPDATA%\Friday`) ;
3. lance **l'agent du PC** au démarrage (tâche « Friday - agent PC », `friday --agent-pc`) :
   le Pi y lit si le PC est allumé, si sa carte graphique est libre, et peut l'éteindre ;
4. garde **Tailscale connecté sans session** (« Run unattended ») ;
5. démarre les deux tâches tout de suite.

À faire à la main dans le **BIOS** : activer le réveil par le réseau (« Wake on LAN »,
« Power On By PCI-E ») et désactiver « ErP Ready » s'il existe. Côté Windows, c'est déjà
bon : carte réseau en « Wake on Magic Packet », démarrage rapide désactivé.

Tout se défait avec `deploy\pc\desinstaller.ps1` (en administrateur).

Côté Pi, dans son `.env` :

```
FRIDAY_PC_AGENT_URL=http://100.87.38.95:8766
FRIDAY_PC_OLLAMA=http://100.87.38.95:11434
FRIDAY_PC_MAC=40:B0:76:A3:D1:15
FRIDAY_PC_BROADCAST=192.168.1.255
```
(+ `FRIDAY_PC_MODEL=qwen3:8b`, `FRIDAY_PC_NUM_CTX=8192` par défaut : les mêmes que le Friday
du PC, pour que le modèle chargé serve aux deux.)
