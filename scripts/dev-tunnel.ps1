# Expoe Django + Vite no celular sem conta (padrao: Cloudflare quick tunnel).
#
# Uso:
#   .\scripts\dev-tunnel.ps1                    # cloudflared - sem cadastro
#   .\scripts\dev-tunnel.ps1 -Provider local    # mesma Wi-Fi, IP da LAN
#   .\scripts\dev-tunnel.ps1 -Provider localtunnel
#   .\scripts\dev-tunnel.ps1 -Provider ngrok      # exige conta ngrok + authtoken
#
# Cloudflared (recomendado, sem conta):
#   winget install Cloudflare.cloudflared

param(
    [ValidateSet("cloudflared", "localtunnel", "local", "ngrok")]
    [string]$Provider = "cloudflared"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$FrontendDir = Join-Path $Root "frontend"
$DjangoPort = if ($env:DJANGO_PORT) { $env:DJANGO_PORT } else { "8000" }
$VitePort = if ($env:VITE_PORT) { $env:VITE_PORT } else { "5173" }

function Wait-HttpOk {
    param([string]$Url, [int]$MaxSeconds = 60)
    $deadline = (Get-Date).AddSeconds($MaxSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch {}
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-LanIPv4 {
    $addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Sort-Object -Property InterfaceMetric
    if ($addrs) { return ($addrs | Select-Object -First 1).IPAddress }
    return $null
}

function Resolve-Binary {
    param([string]$Name, [string]$WingetId)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $link = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\$Name.exe"
    if (Test-Path $link) { return $link }
    if ($WingetId) {
        Write-Host "Instalando $Name ($WingetId)..." -ForegroundColor Yellow
        winget install $WingetId --accept-package-agreements --accept-source-agreements | Out-Null
        $cmd = Get-Command $Name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
        if (Test-Path $link) { return $link }
    }
    throw "$Name nao encontrado. Instale: winget install $WingetId"
}

function Start-DevServers {
    Write-Host "Iniciando Django em 0.0.0.0:$DjangoPort ..." -ForegroundColor Green
    $script:djangoJob = Start-Job -ScriptBlock {
        param($Root, $Port)
        Set-Location $Root
        $env:IS_LOCAL_DEV = "true"
        $env:USE_X_FORWARDED_HOST = "true"
        $env:ALERT_BRIDGE_API_URL = "http://127.0.0.1:$Port/api/internal/alert-bridge/configs/"
        python manage.py runserver "0.0.0.0:$Port"
    } -ArgumentList $Root, $DjangoPort

    Write-Host "Iniciando Vite em 0.0.0.0:$VitePort ..." -ForegroundColor Green
    $script:viteJob = Start-Job -ScriptBlock {
        param($FrontendDir, $Port)
        Set-Location $FrontendDir
        npm run dev -- --host 0.0.0.0 --port $Port
    } -ArgumentList $FrontendDir, $VitePort

    if (-not (Wait-HttpOk "http://127.0.0.1:$DjangoPort/")) {
        Receive-Job $script:djangoJob -ErrorAction SilentlyContinue | Write-Host
        throw "Django nao respondeu na porta $DjangoPort"
    }
    if (-not (Wait-HttpOk "http://127.0.0.1:$VitePort/")) {
        Receive-Job $script:viteJob -ErrorAction SilentlyContinue | Write-Host
        throw "Vite nao respondeu na porta $VitePort"
    }
    Write-Host "Django e Vite OK." -ForegroundColor Green
}

function Show-Urls {
    param([string]$BaseUrl)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Abra no CELULAR:" -ForegroundColor White
    Write-Host "  $BaseUrl" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Login RM:     $BaseUrl/rm/login" -ForegroundColor Gray
    Write-Host "  Login tenant: $BaseUrl/fibramar/login" -ForegroundColor Gray
    Write-Host ""
}

function Stop-All {
    Write-Host "Encerrando..." -ForegroundColor Yellow
    Get-Job -ErrorAction SilentlyContinue | Stop-Job -ErrorAction SilentlyContinue
    Get-Job -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
    foreach ($proc in @("cloudflared", "ngrok", "node")) {
        Get-Process -Name $proc -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "== RM Systems - dev tunnel ($Provider) ==" -ForegroundColor Cyan
Write-Host "Raiz: $Root"
Write-Host ""

$tunnelJob = $null

try {
    Start-DevServers

    switch ($Provider) {
        "local" {
            $ip = Get-LanIPv4
            if (-not $ip) { throw "Nao achei IP da LAN. PC e celular na mesma Wi-Fi?" }
            $base = "http://${ip}:$VitePort"
            Show-Urls $base
            Write-Host "Sem tunel - so funciona na mesma rede Wi-Fi." -ForegroundColor Yellow
            Write-Host "Libere portas $VitePort e $DjangoPort no firewall do Windows se nao abrir." -ForegroundColor DarkGray
            Write-Host "Ctrl+C para encerrar." -ForegroundColor DarkGray
            while ($true) { Start-Sleep -Seconds 5 }
        }

        "cloudflared" {
            $cf = Resolve-Binary "cloudflared" "Cloudflare.cloudflared"
            Write-Host "Tunel Cloudflare (sem conta) -> porta $VitePort ..." -ForegroundColor Green
            $logFile = Join-Path $env:TEMP "rm-cloudflared-$VitePort.log"
            $tunnelJob = Start-Job -ScriptBlock {
                param($Cf, $Port, $Log)
                & $Cf tunnel --url "http://127.0.0.1:$Port" --no-autoupdate 2>&1 |
                    Tee-Object -FilePath $Log
            } -ArgumentList $cf, $VitePort, $logFile

            $publicUrl = $null
            $deadline = (Get-Date).AddSeconds(45)
            while ((Get-Date) -lt $deadline -and -not $publicUrl) {
                Start-Sleep -Seconds 2
                if (Test-Path $logFile) {
                    $text = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
                    if ($text -match "(https://[a-z0-9-]+\.trycloudflare\.com)") {
                        $publicUrl = $Matches[1]
                    }
                }
            }
            if (-not $publicUrl) {
                throw "URL do tunel nao apareceu. Veja $logFile"
            }
            Show-Urls $publicUrl
            Write-Host "Tunel gratuito - URL muda a cada execucao." -ForegroundColor Yellow
            Write-Host "Ctrl+C para encerrar." -ForegroundColor DarkGray
            while ($true) { Start-Sleep -Seconds 5 }
        }

        "localtunnel" {
            Write-Host "Tunel localtunnel (sem conta) -> porta $VitePort ..." -ForegroundColor Green
            $logFile = Join-Path $env:TEMP "rm-localtunnel-$VitePort.log"
            $tunnelJob = Start-Job -ScriptBlock {
                param($Port, $Log, $FrontendDir)
                Set-Location $FrontendDir
                npx --yes localtunnel --port $Port 2>&1 | Tee-Object -FilePath $Log
            } -ArgumentList $VitePort, $logFile, $FrontendDir

            $publicUrl = $null
            $deadline = (Get-Date).AddSeconds(60)
            while ((Get-Date) -lt $deadline -and -not $publicUrl) {
                Start-Sleep -Seconds 2
                if (Test-Path $logFile) {
                    $text = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
                    if ($text -match "(https://[a-z0-9-]+\.loca\.lt)") {
                        $publicUrl = $Matches[1]
                    }
                }
            }
            if (-not $publicUrl) {
                throw "URL do localtunnel nao apareceu. Veja $logFile"
            }
            Show-Urls $publicUrl
            Write-Host "Na 1a visita o localtunnel pode pedir seu IP publico." -ForegroundColor Yellow
            Write-Host "Ctrl+C para encerrar." -ForegroundColor DarkGray
            while ($true) { Start-Sleep -Seconds 5 }
        }

        "ngrok" {
            $ngrok = Resolve-Binary "ngrok" "Ngrok.Ngrok"
            $cfg = Join-Path $env:LOCALAPPDATA "ngrok\ngrok.yml"
            $hasToken = (Test-Path $cfg) -and ((Get-Content $cfg -Raw) -match "authtoken:\s*\S+")
            if (-not $hasToken -and $env:NGROK_AUTHTOKEN) {
                & $ngrok config add-authtoken $env:NGROK_AUTHTOKEN | Out-Null
                $hasToken = $true
            }
            if (-not $hasToken) {
                throw "ngrok exige conta. Use: .\scripts\dev-tunnel.ps1 (cloudflared) ou -Provider local"
            }
            $tunnelJob = Start-Job -ScriptBlock {
                param($Ngrok, $Port)
                & $Ngrok http $Port --log=stdout
            } -ArgumentList $ngrok, $VitePort
            Start-Sleep -Seconds 4
            $json = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
            $publicUrl = ($json.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
            if (-not $publicUrl) { throw "ngrok sem URL publica. Abra http://127.0.0.1:4040" }
            Show-Urls $publicUrl
            Write-Host "Ctrl+C para encerrar." -ForegroundColor DarkGray
            while ($true) { Start-Sleep -Seconds 5 }
        }
    }
} finally {
    Stop-All
}
