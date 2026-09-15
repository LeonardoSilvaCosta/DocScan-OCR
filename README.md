# ScanLayer

CLI Python para adicionar uma camada de texto pesquisável a PDFs escaneados.

## Estrutura

```text
src/scanlayer/     # Pacote instalável, CLI e processamento OCR
tests/            # Testes de contrato e da CLI
scripts/          # Bootstrap Bash e PowerShell
pyproject.toml    # Metadados PEP 621, dependências e ferramentas
Dockerfile        # Execução Linux sem privilégios de root
docker-compose.yml # Execução local com ./data montado em /data
```

## Desenvolvimento

Requer Python 3.11 ou superior. Execute a partir de qualquer diretório:

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\Activate.ps1
```

No Linux/macOS:

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
```

Os scripts criam/reutilizam `.venv`, atualizam pip/setuptools/wheel e instalam
`.[dev]` em modo editável. O script PowerShell aceita `-Python caminho/python.exe`;
o Bash aceita a variável `PYTHON` com o caminho do interpretador.

O bootstrap instala dependências Python. Para processar PDFs, instale também
Tesseract, os dados de idioma português, Ghostscript e unpaper. Em Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-por ghostscript unpaper python3-venv
```

No Windows, use a imagem Docker para ter os executáveis de OCR configurados.

## Uso

```bash
scanlayer --input manual.pdf
scanlayer -i manual.pdf -o resultado.pdf --lang por+eng --no-clean
scanlayer -i ./documentos -o ./resultados
python -m scanlayer --help
```

Sem `--output`, a saída recebe o sufixo `_ocr.pdf`. Entradas que são diretórios
são percorridas recursivamente e sua estrutura relativa é preservada quando
um diretório de saída é informado. Inclinação, limpeza e salto de páginas com
texto estão ativados por padrão; use `--no-deskew`, `--no-clean` e `--force-ocr`
para desativá-los. O retorno da CLI é 0 quando não há falhas, 1 para falhas de
processamento e 2 para argumentos inválidos.

Importação Python: `from scanlayer.processor import process_pdf`.
O módulo anteriormente localizado na raiz foi movido para o pacote `scanlayer`.

## Verificação

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=scanlayer
```

Para executar a suíte rápida e isolada, ative o ambiente virtual e execute `pytest`.
As fixtures criam PDFs de uma página em diretórios temporários exclusivos: uma
imagem com texto desenhado pelo Pillow e um PDF com texto digital criado pelo
`pypdf`. Nenhum documento externo é necessário. Os testes rápidos usam doubles
do motor OCR e verificam também a leitura da saída com `pypdf`.

Para validar o reconhecimento real e a idempotência, execute `pytest --run-ocr`
(ou `pytest --run-ocr -m integration` para executar somente a integração).
Esses testes precisam de Tesseract com o idioma `eng` e Ghostscript instalados;
usam `clean=False` e `deskew=False`, dispensando unpaper. No Debian/Ubuntu,
o pacote do idioma é `tesseract-ocr-eng`. Quando solicitada, a integração falha
se a infraestrutura estiver ausente; no comando padrão, aparece como ignorada.

O intervalo de OCRmyPDF fica na série 16 para estabilizar a API usada pelo módulo.
`typer[all]` é declarado conforme a configuração do projeto; versões recentes
do Typer já incluem Rich e podem avisar que o extra `all` não existe mais.

## Docker

Os wrappers cuidam automaticamente do build da imagem, do bind mount do
diretório atual e do encaminhamento dos argumentos para o ScanLayer:

```bash
./scripts/run.sh -i documento.pdf
```

```powershell
.\scripts\run.ps1 -i documento.pdf
```

No Bash, o container usa o UID/GID atual para que os arquivos gerados pertençam
ao usuário do host. A imagem `scanlayer:latest` é criada automaticamente se
ainda não existir.

Para executar manualmente com Docker Compose:

```powershell
New-Item -ItemType Directory -Force ./data
Copy-Item manual.pdf ./data/entrada.pdf
docker compose config
docker compose build
docker compose run --rm scanlayer --help
docker compose run --rm scanlayer -i entrada.pdf -o saida_ocr.pdf
```

A saída fica em `./data/saida_ocr.pdf`. A pasta `./data` deve existir antes da
execução; o Compose não a cria automaticamente. Em Linux/macOS, use `mkdir -p data`.

A imagem instala o pacote e executa a CLI como `appuser:appuser` (UID/GID 10001),
com `LANG=C.UTF-8` e `LC_ALL=C.UTF-8`. O idioma de OCR continua sendo português.
O locale C.UTF-8 já está disponível na base Debian; não requer gerar pt_BR.

Em Linux, as permissões do bind mount são as da pasta no host e substituem as
permissões de `/data` definidas no build. Para alinhar os IDs com seu usuário:

```bash
mkdir -p data
export APP_UID="$(id -u)" APP_GID="$(id -g)"
docker compose build
docker compose run --rm scanlayer -i entrada.pdf -o saida_ocr.pdf
```

Execute esses comandos com um usuário não-root. Os IDs devem ser positivos e
estar disponíveis na imagem. No PowerShell, podem ser definidos como
`$env:APP_UID = "10001"` e `$env:APP_GID = "10001"` antes do build.
No Docker Desktop, a escrita também depende do compartilhamento da pasta do host.

O uso sem Compose continua disponível:

```powershell
docker build -t scanlayer:local .
docker run --rm --mount "type=bind,source=$($PWD.Path)/data,target=/data" scanlayer:local -i entrada.pdf -o saida_ocr.pdf
```

O contexto de build inclui apenas os arquivos do pacote e sua documentação de
instalação. `.git`, `.venv`, caches, testes, scripts e PDFs locais são excluídos.
