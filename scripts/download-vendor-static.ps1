# Baixa Bootstrap, Chart.js e Leaflet para static/vendor/ (CSP sem CDNs em script-src)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Vendor = Join-Path $Root "static\vendor"
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null

$assets = @(
    @{
        Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
        Out = "bootstrap\5.3.3\css\bootstrap.min.css"
    },
    @{
        Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        Out = "bootstrap\5.3.3\js\bootstrap.bundle.min.js"
    },
    @{
        Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css"
        Out = "bootstrap\5.1.3\css\bootstrap.min.css"
    },
    @{
        Url = "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"
        Out = "bootstrap\5.1.3\js\bootstrap.bundle.min.js"
    },
    @{
        Url = "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"
        Out = "chart.js\4.4.4\chart.umd.min.js"
    },
    @{
        Url = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
        Out = "chart.js\4.4.1\chart.umd.min.js"
    },
    @{
        Url = "https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"
        Out = "leaflet\1.7.1\leaflet.css"
    },
    @{
        Url = "https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"
        Out = "leaflet\1.7.1\leaflet.js"
    },
    @{
        Url = "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png"
        Out = "leaflet\1.7.1\images\marker-icon.png"
    },
    @{
        Url = "https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png"
        Out = "leaflet\1.7.1\images\marker-shadow.png"
    },
    @{
        Url = "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png"
        Out = "leaflet\1.7.1\images\marker-icon-2x.png"
    },
    @{
        Url = "https://unpkg.com/leaflet@1.7.1/dist/images/layers.png"
        Out = "leaflet\1.7.1\images\layers.png"
    },
    @{
        Url = "https://unpkg.com/leaflet@1.7.1/dist/images/layers-2x.png"
        Out = "leaflet\1.7.1\images\layers-2x.png"
    }
)

foreach ($a in $assets) {
    $dest = Join-Path $Vendor $a.Out
    $dir = Split-Path $dest -Parent
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host ">> $($a.Out)"
    Invoke-WebRequest -Uri $a.Url -OutFile $dest -UseBasicParsing
}
Write-Host "OK - vendor em $Vendor" -ForegroundColor Green
