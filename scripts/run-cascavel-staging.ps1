# Scan CASCAVEL contra RM Systems (Windows / PowerShell).
# Uso: .\scripts\run-cascavel-staging.ps1
# Env: $env:BASE_URL, $env:CASCAVEL_DIR, $env:SKIP_SERVER_CHECK

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BaseUrl = if ($env:BASE_URL) { $env:BASE_URL } else { "http://127.0.0.1:8000" }
$CascavelDir = if ($env:CASCAVEL_DIR) { $env:CASCAVEL_DIR } else { Join-Path $Root "tools\Cascavel" }
# Perfil padrao: rmsys (17 plugins acionaveis). Scan completo: $env:PROFILE='web'
$Profile = if ($env:PROFILE) { $env:PROFILE } else { "rmsys" }
$ReportsDir = Join-Path $Root "reports\cascavel"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $ReportsDir "scan-$Timestamp.log"

# Windows: evita UnicodeEncodeError (emojis Rich/cp1252)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:NO_COLOR = "1"
if ($Host.UI.RawUI) { try { chcp 65001 | Out-Null } catch {} }

function Get-CascavelTargetFromUrl {
    param([string]$Url)
    $u = $Url.Trim().TrimEnd("/")
    if ($u -match "^https?://(.+)$") { $u = $Matches[1] }
    $u = ($u -split "/")[0]
    $u = ($u -split "\?")[0]
    return $u
}

$CascavelTarget = Get-CascavelTargetFromUrl $BaseUrl

New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null

Write-Host "== RM Systems x CASCAVEL ==" -ForegroundColor Cyan
Write-Host "BASE_URL:        $BaseUrl"
Write-Host "CASCAVEL target: $CascavelTarget  (use --allow-localhost)"
Write-Host "CASCAVEL dir:    $CascavelDir"
Write-Host "Relatorios RM:   $ReportsDir"
Write-Host ""

if ($env:SKIP_SERVER_CHECK -ne "1") {
    Write-Host ">> Verificando Django em $BaseUrl/health/ ..."
    try {
        $null = Invoke-WebRequest -Uri "$BaseUrl/health/" -UseBasicParsing -TimeoutSec 10
        Write-Host "OK - servidor ativo." -ForegroundColor Green
    } catch {
        Write-Host "ERRO: Django nao responde em $BaseUrl" -ForegroundColor Red
        Write-Host "Inicie: py manage.py runserver"
        exit 1
    }
}

if (-not (Test-Path (Join-Path $CascavelDir "cascavel.py"))) {
    Write-Host "ERRO: Clone CASCAVEL em $CascavelDir" -ForegroundColor Red
    Write-Host 'git clone https://github.com/glferreira-devsecops/Cascavel.git tools\Cascavel'
    exit 1
}

$VenvPython = Join-Path $CascavelDir "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host ">> Criando venv CASCAVEL ..."
    python -m venv (Join-Path $CascavelDir "venv")
    & $VenvPython -m pip install -q -r (Join-Path $CascavelDir "requirements.txt")
}

$CascavelArgs = @(
    "cascavel.py",
    "-t", $CascavelTarget,
    "--allow-localhost",
    "--plugins-only",
    "--profile", $Profile,
    "-q",
    "-o", "json",
    "--no-preloader",
    "--no-notify",
    "--timeout", "120"
)
# CASCAVEL abre menu interativo pos-scan; "0" encerra (ASCII sem BOM).
$stdinFile = Join-Path $env:TEMP "cascavel-menu-0.txt"
[System.IO.File]::WriteAllText($stdinFile, "0`n", (New-Object System.Text.UTF8Encoding $false))

Write-Host ">> Scan CASCAVEL (plugins-only, profile=$Profile) ..."
Write-Host "   $($CascavelArgs -join ' ')"
Push-Location $CascavelDir
$scanExit = 0
try {
    cmd /c "echo 0| `"$VenvPython`" $($CascavelArgs -join ' ')" 2>&1 | Tee-Object -FilePath $LogFile
    $scanExit = $LASTEXITCODE
} catch {
    $_ | Out-String | Tee-Object -FilePath $LogFile -Append
    $scanExit = 1
} finally {
    Pop-Location
}

# Copia relatorios gerados em tools/Cascavel/reports/ para o repo
$CascavelReports = Join-Path $CascavelDir "reports"
if (Test-Path $CascavelReports) {
    $dest = Join-Path $ReportsDir "cascavel-export-$Timestamp"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $CascavelReports "*") -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ">> Export copiado para: $dest" -ForegroundColor Green
}

Write-Host ""
if ($scanExit -ne 0) {
    Write-Host "Scan terminou com codigo $scanExit - veja $LogFile" -ForegroundColor Yellow
} else {
    Write-Host "Scan concluido." -ForegroundColor Green
}
Write-Host "Log: $LogFile"
Get-ChildItem $ReportsDir -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 8 | Format-Table Name, Length, LastWriteTime

exit $scanExit
