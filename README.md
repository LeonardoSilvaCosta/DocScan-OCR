# ScanLayer

O ScanLayer é uma ferramenta de linha de comando (CLI) para adicionar uma
camada de texto pesquisável a PDFs escaneados. Ele usa o OCRmyPDF, o Tesseract
e ferramentas auxiliares para reconhecer o texto sem alterar o arquivo de
entrada.

Este guia mostra, passo a passo, como instalar, executar e conferir o
resultado.

## O que a aplicação faz

Ao processar um PDF digitalizado, o ScanLayer:

1. lê as páginas do documento;
2. corrige pequenas inclinações, quando necessário;
3. reduz ruídos da imagem;
4. reconhece o texto com o Tesseract;
5. grava um novo PDF com uma camada de texto invisível.

O PDF gerado continua visualmente semelhante ao original, mas passa a permitir
pesquisa, seleção e cópia do texto. Pela CLI, o arquivo original nunca é
sobrescrito.

## Pré-requisitos

É necessário ter:

- Python 3.11 ou superior, para execução local;
- Tesseract OCR;
- os dados de idioma do Tesseract usados no processamento;
- Ghostscript;
- unpaper, usado pela limpeza das páginas.

No Windows, a forma mais simples é usar Docker, pois ele já fornece os
executáveis e os dados de OCR necessários. Para execução local em Debian ou
Ubuntu, instale as dependências do sistema antes de criar o ambiente Python:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-por ghostscript unpaper python3-venv
```

Se também for executar os testes de integração, instale o idioma inglês:

```bash
sudo apt-get install tesseract-ocr-eng
```

## Opção recomendada: executar com Docker

Esta opção não exige instalar Tesseract, Ghostscript ou unpaper no computador.
É necessário apenas ter o Docker instalado e em execução.

### 1. Coloque o PDF em uma pasta de trabalho

Abra um terminal na pasta que contém o documento. Por exemplo:

```text
meu-projeto/
├── contrato.pdf
└── outros-documentos/
```

### 2. Execute o ScanLayer

No Linux/macOS:

```bash
/caminho/para/scanlayer/scripts/run.sh -i contrato.pdf -o contrato_ocr.pdf
```

No Windows PowerShell, a partir da pasta do projeto:

```powershell
.\scripts\run.ps1 -i contrato.pdf -o contrato_ocr.pdf
```

Na primeira execução, o wrapper constrói automaticamente a imagem
`scanlayer:latest`. Nas execuções seguintes, ele reutiliza essa imagem.

O arquivo `contrato_ocr.pdf` será criado na pasta atual. O wrapper monta a
pasta atual em `/data` dentro do container, portanto os caminhos informados
devem ser relativos a essa pasta.

### 3. Processar todos os PDFs de uma pasta

```powershell
.\scripts\run.ps1 -i .\documentos -o .\resultados
```

O processamento é recursivo. A estrutura de subpastas de `documentos` é
mantida dentro de `resultados`. Por exemplo:

```text
documentos/2025/contrato.pdf
        ↓
resultados/2025/contrato_ocr.pdf
```

No Linux/macOS, use o mesmo comando com o wrapper Bash:

```bash
./scripts/run.sh -i ./documentos -o ./resultados
```

### Alternativa: Docker Compose

O Compose usa `./data` como pasta de entrada e saída. Crie a pasta e copie o
arquivo para ela:

```powershell
New-Item -ItemType Directory -Force ./data
Copy-Item contrato.pdf ./data/entrada.pdf
docker compose build
docker compose run --rm scanlayer -i entrada.pdf -o saida_ocr.pdf
```

O resultado ficará em `./data/saida_ocr.pdf`. No Linux/macOS, crie a pasta com
`mkdir -p data`.

## Execução local com Python

Use esta opção quando Tesseract, Ghostscript e unpaper já estiverem instalados
no sistema.

### 1. Crie o ambiente virtual

No Windows PowerShell:

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\Activate.ps1
```

No Linux/macOS:

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
```

Os scripts criam ou reutilizam `.venv`, atualizam as ferramentas de instalação
e instalam o ScanLayer em modo editável, junto com as dependências de
desenvolvimento.

Se houver mais de uma instalação do Python, é possível indicar qual usar:

```powershell
.\scripts\bootstrap.ps1 -Python C:\Python311\python.exe
```

No Linux/macOS, use a variável `PYTHON`:

```bash
PYTHON=/caminho/para/python3 bash scripts/bootstrap.sh
```

### 2. Processe um PDF

Com o ambiente virtual ativado:

```bash
scanlayer -i contrato.pdf -o contrato_ocr.pdf
```

Também é possível usar o módulo Python diretamente:

```bash
python -m scanlayer -i contrato.pdf -o contrato_ocr.pdf
```

Se `--output` não for informado, a saída será criada ao lado do original com
o sufixo `_ocr`:

```bash
scanlayer --input contrato.pdf
# cria contrato_ocr.pdf
```

## Opções da CLI

| Opção | Descrição | Padrão |
| --- | --- | --- |
| `-i`, `--input` | PDF ou diretório de PDFs de entrada | obrigatório |
| `-o`, `--output` | Arquivo de saída ou diretório de destino | `<nome>_ocr.pdf` |
| `--lang` | Idiomas do OCR separados por `+`, como `por+eng` | `por` |
| `--deskew` / `--no-deskew` | Corrige ou não a inclinação das páginas | ativado |
| `--clean` / `--no-clean` | Remove ou não ruídos com unpaper | ativado |
| `--skip-text` / `--force-ocr` | Ignora páginas que já têm texto ou força OCR em todas | `--skip-text` |
| `-v`, `--verbose` | Exibe informações detalhadas para diagnóstico | desativado |
| `--help` | Mostra a ajuda da ferramenta | — |

### Exemplos práticos

PDF em português e inglês:

```bash
scanlayer -i manual.pdf -o manual_ocr.pdf --lang por+eng
```

PDF com páginas que já possuem texto, mantendo esse texto sem forçar novo OCR:

```bash
scanlayer -i documento.pdf --skip-text
```

Forçar o reconhecimento em todas as páginas e desativar a limpeza:

```bash
scanlayer -i documento.pdf -o resultado.pdf --force-ocr --no-clean
```

Ver todas as opções disponíveis:

```bash
scanlayer --help
```

## Regras importantes de processamento

- Apenas arquivos com extensão `.pdf` são aceitos.
- A entrada e a saída devem ser arquivos diferentes.
- Se a saída já existir, o arquivo é pulado; a aplicação não o sobrescreve.
- Em um lote, arquivos cujo nome já termina em `_ocr.pdf` são pulados para
  evitar reprocessamento acidental.
- Para processar novamente um documento, escolha outro nome ou remova/mova a
  saída anterior com segurança antes de executar o comando.
- Idiomas são códigos do Tesseract. Para português e inglês, use `por+eng`.
  Cada idioma informado precisa estar instalado no ambiente de execução.
- O nome de saída de um lote é formado pelo nome original acrescido de
  `_ocr.pdf`, preservando os diretórios relativos.

A CLI retorna código `0` quando todos os arquivos terminam com sucesso ou são
pulados, `1` quando pelo menos um arquivo falha e `2` quando os argumentos são
inválidos.

## Conferindo o resultado

Abra o PDF gerado em um leitor que permita selecionar texto. Para uma
verificação rápida, tente:

1. selecionar uma palavra com o mouse;
2. copiar e colar o trecho em um editor de texto;
3. pesquisar uma palavra usando `Ctrl+F` (Windows/Linux) ou `Cmd+F` (macOS).

O OCR pode cometer erros em documentos inclinados, com baixa resolução,
manuscritos, carimbos ou fontes pouco legíveis. Nesses casos, experimente
`--lang` com todos os idiomas presentes e compare o resultado visual com o
documento original.

## Solução de problemas

### “Tesseract”, “Ghostscript” ou “unpaper” não encontrado

Na execução local, confirme que os programas estão instalados e disponíveis no
`PATH`. No Windows, prefira os wrappers Docker e confirme que o Docker Desktop
está aberto.

### O idioma `por` não está disponível

Instale os dados de português do Tesseract (`tesseract-ocr-por` no Debian/
Ubuntu). Para confirmar os idiomas disponíveis:

```bash
tesseract --list-langs
```

### Ghostscript 10.0.0 a 10.02.0 bloqueado pelo OCRmyPDF

Essas versões podem corromper PDFs que já contêm texto ao usar
`--skip-text`. A imagem atual exige Ghostscript 10.03.0 ou superior. Reconstrua
a imagem para substituir uma versão antiga em cache:

```powershell
docker build --pull --no-cache --tag scanlayer:latest .
```

Com Docker Compose, use:

```powershell
docker compose build --pull --no-cache
```

### Nenhum PDF foi encontrado

Verifique se o caminho passado em `--input` existe e se a pasta contém arquivos
com extensão `.pdf`. Em comandos Docker, lembre-se de que o caminho é relativo
à pasta atual montada no container.

### O arquivo foi pulado

A saída de destino já existe ou o arquivo parece ser uma saída anterior com
sufixo `_ocr`. Use outro diretório/nome de saída ou mova a saída anterior antes
de executar novamente.

### Diagnóstico detalhado

Adicione `--verbose` ao comando:

```bash
scanlayer -i documento.pdf -o resultado.pdf --verbose
```

## Desenvolvimento e testes

Depois de ativar o ambiente virtual, execute:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov=scanlayer
```

Os testes padrão são rápidos e não dependem de documentos externos. Para
executar os testes de integração com OCR real:

```bash
pytest --run-ocr
```

Esses testes exigem Tesseract com `eng` e Ghostscript instalados. O marcador
`integration` permite executar somente a integração:

```bash
pytest --run-ocr -m integration
```

## Estrutura do projeto

```text
src/scanlayer/       pacote Python, CLI e processamento OCR
tests/               testes unitários, de contrato e integração
scripts/             scripts de bootstrap e wrappers Docker
pyproject.toml       metadados, dependências e ferramentas do projeto
Dockerfile           imagem Linux para execução sem root
docker-compose.yml   configuração Compose com ./data montado em /data
```

## Uso como biblioteca

Para integrar o processamento em outro código Python, importe a função
`process_pdf`:

```python
from pathlib import Path

from scanlayer.processor import process_pdf

sucesso = process_pdf(
    Path("entrada.pdf"),
    Path("saida_ocr.pdf"),
    lang="por+eng",
)
```

A função retorna `True` quando o PDF de saída é criado com sucesso e `False`
quando ocorre uma falha esperada de validação, dependência ou processamento.
