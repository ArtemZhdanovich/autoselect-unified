<#
    make.ps1 — те же цели, что в Makefile, для Windows (где `make` обычно нет).

    Примеры:
        .\make.ps1 test
        .\make.ps1 up-bot
        .\make.ps1 up-backend
        .\make.ps1 up-all
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'install', 'test', 'test-contract', 'up-bot', 'up-backend', 'up-miniapp', 'dev', 'up-edge', 'up-edge-tunnel', 'up-edge-le', 'docker-bot', 'docker-backend', 'docker-miniapp', 'docker-edge', 'up-all', 'clean')]
    [string]$Target = 'help',

    [ValidateSet('mock', 'real')]
    [string]$Mode = 'mock'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# PYTHONPATH — как в Makefile: корень + оба сервиса.
$env:PYTHONPATH = "$root;$root\bot-service;$root\backend-service"

function Invoke-Python {
    param([string[]]$Arguments)
    & python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "python завершился с кодом $LASTEXITCODE" }
}

switch ($Target) {
    'help' {
        Write-Host "make.ps1 install        - поставить зависимости"
        Write-Host "make.ps1 test           - все тесты"
        Write-Host "make.ps1 test-contract  - только контрактные тесты"
        Write-Host "make.ps1 up-bot         - бот без бэкенда (SERVICE=bot MODE=mock)"
        Write-Host "make.ps1 up-backend     - только домен (SERVICE=backend MODE=mock)"
        Write-Host "make.ps1 up-miniapp     - Mini App: статика + прокси на :8080"
        Write-Host "make.ps1 dev            - backend + Mini App одной командой"
        Write-Host "make.ps1 up-edge        - HTTPS локально (self-signed, :8081/:8443)"
        Write-Host "make.ps1 up-edge-tunnel - публичный HTTPS через туннель"
        Write-Host "make.ps1 up-edge-le     - Let's Encrypt (нужны DOMAIN и ACME_EMAIL)"
        Write-Host "make.ps1 up-all         - полный стек в docker (профиль all)"
    }
    'install' {
        Invoke-Python @('-m', 'pip', 'install', '--quiet',
            'aiogram>=3.13,<4', 'fastapi>=0.110,<1', 'uvicorn>=0.27,<1',
            'httpx>=0.27,<1', 'pydantic>=2.7,<3', 'pytest', 'pyyaml')
    }
    'test' {
        Invoke-Python @('-m', 'pytest', 'tests', '-q')
    }
    'test-contract' {
        Invoke-Python @('-m', 'pytest', 'tests', '-q', '-k', 'contract')
    }
    'up-bot' {
        $env:SERVICE = 'bot'; $env:MODE = $Mode
        Invoke-Python @('scripts/run_bot.py')
    }
    'up-backend' {
        $env:SERVICE = 'backend'; $env:MODE = $Mode
        Invoke-Python @('scripts/run_backend.py', '--port', '8000')
    }
    'up-miniapp' {
        Invoke-Python @('scripts/run_miniapp.py', '--port', '8080')
    }
    'dev' {
        Invoke-Python @('scripts/dev_stack.py')
    }
    'up-edge' {
        $env:TLS_MODE = 'selfsigned'; $env:EDGE_HTTP_PORT = '8081'; $env:EDGE_HTTPS_PORT = '8443'
        Invoke-Python @('scripts/run_edge.py')
    }
    'up-edge-tunnel' {
        $env:TLS_MODE = 'tunnel'
        if (-not $env:TUNNEL_PROVIDER) { $env:TUNNEL_PROVIDER = 'tunnelmole' }
        Invoke-Python @('scripts/run_edge.py')
    }
    'up-edge-le' {
        $env:TLS_MODE = 'letsencrypt'
        Invoke-Python @('scripts/run_edge.py')
    }
    'docker-bot' {
        docker compose --profile bot-only up --build
    }
    'docker-backend' {
        docker compose --profile backend-only up --build
    }
    'docker-miniapp' {
        docker compose --profile miniapp-only up --build
    }
    'docker-edge' {
        docker compose --profile edge up --build
    }
    'up-all' {
        docker compose --profile all up --build
    }
    'clean' {
        Get-ChildItem -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
    }
}
