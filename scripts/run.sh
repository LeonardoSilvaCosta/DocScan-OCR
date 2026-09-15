#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="scanlayer:latest"
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_DIRECTORY="$(pwd -P)"

if ! command -v docker >/dev/null 2>&1; then
    printf '%s\n' 'Erro: o Docker não está instalado ou não foi encontrado no PATH.' >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    printf '%s\n' 'Erro: o daemon do Docker não está em execução ou não está acessível.' >&2
    printf '%s\n' 'Inicie o Docker e tente novamente.' >&2
    exit 1
fi

if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    printf 'Imagem %s não encontrada; iniciando build...\n' "$IMAGE_NAME"
    docker build --tag "$IMAGE_NAME" "$PROJECT_ROOT"
fi

exec docker run \
    --rm \
    --user "$(id -u):$(id -g)" \
    --mount "type=bind,source=${HOST_DIRECTORY},target=/data" \
    --workdir /data \
    "$IMAGE_NAME" \
    "$@"
