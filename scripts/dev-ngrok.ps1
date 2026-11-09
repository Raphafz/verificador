# Atalho — usa cloudflared (sem conta). Ver scripts/dev-tunnel.ps1
& (Join-Path $PSScriptRoot "dev-tunnel.ps1") -Provider ngrok @args
