$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$ImageName = "scanlayer:latest"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CurrentDirectory = (Get-Location).ProviderPath

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    [Console]::Error.WriteLine("Erro: o Docker não está instalado ou não foi encontrado no PATH.")
    exit 1
}

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine(
        "Erro: o daemon do Docker não está em execução ou não está acessível. " +
        "Inicie o Docker e tente novamente."
    )
    exit 1
}

& docker image inspect $ImageName *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Imagem $ImageName não encontrada; iniciando build..."
    & docker build --tag $ImageName $ProjectRoot
    if ($LASTEXITCODE -ne 0) {
        [Console]::Error.WriteLine("Erro: não foi possível construir a imagem $ImageName.")
        exit 1
    }
}

& docker run `
    --rm `
    --mount "type=bind,source=$CurrentDirectory,target=/data" `
    --workdir /data `
    $ImageName `
    @args
exit $LASTEXITCODE
