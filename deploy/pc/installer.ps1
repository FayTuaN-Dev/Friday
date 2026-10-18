# Friday : le PC pret a etre allume, vu et eteint par le Raspberry Pi (R4), et a lui preter
# sa carte graphique (R5). A lancer UNE fois, en administrateur :
#   clic droit sur PowerShell > Executer en tant qu'administrateur, puis
#   powershell -ExecutionPolicy Bypass -File deploy\pc\installer.ps1
# Tout se defait avec deploy\pc\desinstaller.ps1.
$ErrorActionPreference = "Stop"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "A lancer en administrateur." -ForegroundColor Red; exit 1 }

$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
$user = "$env:USERDOMAIN\$env:USERNAME"
$tailnet = "100.64.0.0/10"

Write-Host "1/5 Pare-feu : Ollama (11434) et l'agent (8766) ouverts au seul reseau Tailscale"
foreach ($rule in @(@{Name = "Friday - Ollama (Tailscale)"; Port = 11434},
                    @{Name = "Friday - agent PC (Tailscale)"; Port = 8766})) {
    Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol TCP `
        -LocalPort $rule.Port -RemoteAddress $tailnet -Action Allow -Profile Any | Out-Null
}

Write-Host "2/5 Ollama au demarrage de Windows, sans session (tache planifiee)"
$startup = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Ollama.lnk"
$kept = "$env:LOCALAPPDATA\Friday"
New-Item -ItemType Directory -Force $kept | Out-Null
if (Test-Path $startup) {  # sinon, a l'ouverture de session, l'appli d'Ollama en lancerait un 2e
    Move-Item $startup "$kept\Ollama.lnk" -Force
}
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$boot = New-ScheduledTaskTrigger -AtStartup
# 0.0.0.0 : le Pi le joint par Tailscale ; le pare-feu (1/5) n'ouvre le port qu'a Tailscale
New-Item -ItemType Directory -Force $kept | Out-Null
$exe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
Set-Content "$kept\ollama-serveur.cmd" -Encoding ASCII -Value @(
    "@echo off", "set OLLAMA_HOST=0.0.0.0:11434", "set OLLAMA_MODELS=$env:USERPROFILE\.ollama\models",
    "`"$exe`" serve")
$ollama = New-ScheduledTaskAction -Execute "$kept\ollama-serveur.cmd"
Register-ScheduledTask -TaskName "Friday - Ollama" -Action $ollama -Trigger $boot `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "3/5 L'agent du PC au demarrage (le Pi le voit allume et peut l'eteindre)"
$agent = New-ScheduledTaskAction -Execute "$repo\.venv\Scripts\pythonw.exe" `
    -Argument "-m friday --agent-pc" -WorkingDirectory $repo
Register-ScheduledTask -TaskName "Friday - agent PC" -Action $agent -Trigger $boot `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "4/5 Tailscale connecte meme sans session ouverte"
& "C:\Program Files\Tailscale\tailscale.exe" set --unattended=true
if ($LASTEXITCODE -ne 0) {
    Write-Host "   A faire a la main : icone Tailscale > Settings > Run unattended" -ForegroundColor Yellow
}

Write-Host "5/5 Demarrage des deux taches maintenant (Ollama redemarre : quelques secondes)"
Get-Process "ollama app", "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName "Friday - Ollama"
Start-ScheduledTask -TaskName "Friday - agent PC"
Start-Sleep -Seconds 5
try {
    Invoke-RestMethod http://127.0.0.1:11434/api/version | Out-Null
    Write-Host "   Ollama repond." -ForegroundColor Green
} catch { Write-Host "   Ollama ne repond pas encore : voir le Planificateur de taches." -ForegroundColor Yellow }

Write-Host ""
Write-Host "Fini. Reste UNE chose a faire a la main, dans le BIOS (touche Suppr ou F2 au demarrage) :"
Write-Host "  activer le reveil par le reseau : "Wake on LAN" / "Power On By PCI-E","
Write-Host "  et desactiver "ErP Ready" s'il existe (sinon la carte reseau s'eteint avec le PC)."
