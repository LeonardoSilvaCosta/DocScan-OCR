[CmdletBinding()]
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $ProjectRoot
try {
    & $Python -c 'import sys; sys.exit(int(sys.version_info < (3, 11)))'
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 ou superior é necessário." }
    $VenvPython = Join-Path $ProjectRoot ".venv/Scripts/python.exe"
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual." }
    & $VenvPython -m pip install --upgrade pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar as ferramentas de instalação." }
    & $VenvPython -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar ScanLayer e dependências de desenvolvimento." }
    Write-Host 'Bootstrap concluído. Ative com: .\.venv\Scripts\Activate.ps1'
}
finally {
    Pop-Location
}
