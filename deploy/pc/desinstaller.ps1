# Defait deploy\pc\installer.ps1 (en administrateur) : taches, regles du pare-feu, et remet
# l'appli d'Ollama au demarrage de la session.
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "A lancer en administrateur." -ForegroundColor Red; exit 1 }
foreach ($task in "Friday - Ollama", "Friday - agent PC") {
    Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
}
foreach ($name in "Friday - Ollama (Tailscale)", "Friday - agent PC (Tailscale)") {
    Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
}
$kept = "$env:LOCALAPPDATA\Friday\Ollama.lnk"
if (Test-Path $kept) {
    Move-Item $kept "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Ollama.lnk" -Force
}
Get-Process "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
Write-Host "Defait : Ollama redemarre comme avant (avec la session)." -ForegroundColor Green
