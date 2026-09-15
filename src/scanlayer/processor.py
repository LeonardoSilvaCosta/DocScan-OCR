"""Processamento de PDFs escaneados com OCRmyPDF.

Este módulo não configura handlers de logging. A aplicação que o utiliza deve
configurar o formato e o destino dos logs no ponto de entrada do processo.
"""

from __future__ import annotations

import errno
import logging
import os
import re
from pathlib import Path

import ocrmypdf
from ocrmypdf.exceptions import (
    BadArgsError,
    DpiError,
    EncryptedPdfError,
    InputFileError,
    MissingDependencyError,
    OutputFileAccessError,
    PriorOcrFoundError,
    SubprocessOutputError,
    TesseractConfigError,
    UnsupportedImageFormatError,
)

logger = logging.getLogger(__name__)

_PDF_SIGNATURE = b"%PDF-"
_PDF_HEADER_LENGTH = 1024
_LANGUAGE_CODE = re.compile(r"^[A-Za-z0-9_/-]+$")


def _validate_paths(input_path: Path, output_path: Path) -> bool:
    """Valida os caminhos sem criar ou sobrescrever o arquivo de saída."""
    if input_path.suffix.lower() != ".pdf":
        logger.error("O arquivo de entrada não possui extensão .pdf: %s", input_path)
        return False

    if output_path.suffix.lower() != ".pdf":
        logger.error("O arquivo de saída não possui extensão .pdf: %s", output_path)
        return False

    try:
        if not input_path.exists():
            logger.error("Arquivo de entrada não encontrado: %s", input_path)
            return False
        if not input_path.is_file():
            logger.error("O caminho de entrada não é um arquivo regular: %s", input_path)
            return False
        if input_path.stat().st_size == 0:
            logger.error("O arquivo de entrada está vazio: %s", input_path)
            return False

        # Aceita cabeçalhos PDF encontrados nos primeiros 1024 bytes.
        with input_path.open("rb") as pdf_file:
            header = pdf_file.read(_PDF_HEADER_LENGTH)
        if _PDF_SIGNATURE not in header:
            logger.error("Assinatura PDF ausente ou inválida: %s", input_path)
            return False

        if input_path.resolve() == output_path.resolve():
            logger.error("Entrada e saída devem apontar para arquivos diferentes: %s", input_path)
            return False

        output_parent = output_path.parent
        if not output_parent.exists() or not output_parent.is_dir():
            logger.error("Diretório de saída inexistente ou inválido: %s", output_parent)
            return False
        if not os.access(output_parent, os.W_OK):
            logger.error("Diretório de saída sem permissão de escrita: %s", output_parent)
            return False
        if output_path.exists() and not output_path.is_file():
            logger.error("O caminho de saída não é um arquivo regular: %s", output_path)
            return False
        if output_path.exists() and not os.access(output_path, os.W_OK):
            logger.error("Arquivo de saída sem permissão de escrita: %s", output_path)
            return False
    except (OSError, ValueError) as exc:
        logger.error("Não foi possível validar os caminhos do PDF: %s", exc)
        return False

    return True


def _parse_languages(lang: str) -> list[str] | None:
    """Converte ``por+eng`` em uma lista aceita pela API do OCRmyPDF."""
    languages = [code.strip() for code in lang.split("+") if code.strip()]
    if not languages or any(_LANGUAGE_CODE.fullmatch(code) is None for code in languages):
        logger.error("Código de idioma OCR inválido: %r", lang)
        return None
    return languages


def process_pdf(
    input_path: Path,
    output_path: Path,
    lang: str = "por",
    deskew: bool = True,
    clean: bool = True,
    skip_text: bool = True,
) -> bool:
    """Adiciona uma camada de texto OCR a um PDF.

    Retorna ``True`` somente quando o OCRmyPDF conclui e grava a saída. Falhas
    esperadas são registradas e retornam ``False``; elas não escapam para o
    chamador. ``KeyboardInterrupt`` e ``SystemExit`` continuam sendo propagados.

    Args:
        input_path: PDF de origem.
        output_path: PDF de destino, diferente do arquivo de origem.
        lang: Um idioma Tesseract ou vários separados por ``+`` (por exemplo,
            ``"por+eng"``).
        deskew: Corrige pequenas inclinações das páginas.
        clean: Limpa ruído antes do reconhecimento.
        skip_text: Ignora páginas que já possuem texto em vez de interromper.
    """
    if not isinstance(input_path, Path) or not isinstance(output_path, Path):
        logger.error("input_path e output_path devem ser instâncias de pathlib.Path")
        return False

    languages = _parse_languages(lang)
    if languages is None or not _validate_paths(input_path, output_path):
        return False

    logger.info(
        "Iniciando OCR: entrada=%s saída=%s idiomas=%s",
        input_path,
        output_path,
        "+".join(languages),
    )

    try:
        exit_code = ocrmypdf.ocr(
            input_path,
            output_path,
            language=languages,
            deskew=deskew,
            clean=clean,
            skip_text=skip_text,
            progress_bar=False,
        )
    except PriorOcrFoundError as exc:
        logger.warning(
            "O PDF já contém texto/OCR; ative skip_text para ignorar essas páginas: %s",
            exc,
        )
        return False
    except (InputFileError, UnsupportedImageFormatError, DpiError, EncryptedPdfError) as exc:
        logger.error("PDF inválido, corrompido, criptografado ou não suportado: %s", exc)
        return False
    except OutputFileAccessError as exc:
        logger.error("Não foi possível criar o PDF de saída: %s", exc)
        return False
    except MissingDependencyError as exc:
        logger.error("Dependência externa do OCRmyPDF não está disponível: %s", exc)
        return False
    except (TesseractConfigError, SubprocessOutputError) as exc:
        logger.error("Falha no motor OCR/Tesseract: %s", exc)
        return False
    except BadArgsError as exc:
        logger.error("Configuração inválida para o OCRmyPDF: %s", exc)
        return False
    except MemoryError:
        logger.exception("Memória insuficiente durante o processamento de %s", input_path)
        return False
    except OSError as exc:
        if exc.errno == errno.ENOMEM:
            logger.exception("Memória insuficiente durante o processamento de %s", input_path)
        else:
            logger.exception("Falha de sistema de arquivos ou processo durante o OCR: %s", exc)
        return False
    except Exception:
        # Mantém o contrato booleano na fronteira de processamento e registra o
        # traceback para que falhas inesperadas continuem diagnosticáveis.
        logger.exception("Falha inesperada ao processar o PDF %s", input_path)
        return False

    try:
        if int(exit_code) != 0:
            logger.error("OCRmyPDF terminou com código de saída %s", exit_code)
            return False
        if not output_path.is_file() or output_path.stat().st_size == 0:
            logger.error("OCRmyPDF terminou sem produzir um PDF de saída válido: %s", output_path)
            return False
    except (OSError, TypeError, ValueError) as exc:
        logger.error("Não foi possível validar o resultado do OCR: %s", exc)
        return False

    logger.info("OCR concluído com sucesso: %s", output_path)
    return True
