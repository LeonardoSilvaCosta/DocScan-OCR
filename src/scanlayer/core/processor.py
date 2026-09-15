"""Execução do pipeline OCR e tradução de erros de infraestrutura."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from time import perf_counter

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


class OCRDomainError(Exception):
    """Classe-base das falhas esperadas na fronteira de OCR."""


class CorruptedPDFError(OCRDomainError):
    """O arquivo informado não é um PDF utilizável pelo pipeline."""


class OCRProcessingError(OCRDomainError):
    """O motor OCR não conseguiu concluir o processamento."""


class FileAccessError(OCRDomainError):
    """Um caminho de entrada ou saída não pôde ser acessado."""


def _log(
    level: int,
    message: str,
    *,
    input_path: Path,
    output_path: Path,
    started_at: float,
    status: str,
    exc_info: bool = False,
) -> None:
    """Registra um evento com campos extras consumíveis por formatadores JSON."""
    logger.log(
        level,
        message,
        extra={
            "input_file": input_path.name,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "elapsed_seconds": round(perf_counter() - started_at, 6),
            "status": status,
        },
        exc_info=exc_info,
    )


def _parse_languages(lang: str) -> list[str]:
    if not isinstance(lang, str):
        raise OCRProcessingError("O idioma OCR deve ser uma string.")

    languages = [code.strip() for code in lang.split("+") if code.strip()]
    if not languages or any(_LANGUAGE_CODE.fullmatch(code) is None for code in languages):
        raise OCRProcessingError(f"Código de idioma OCR inválido: {lang!r}.")
    return languages


def _validate_input(input_path: Path) -> None:
    if input_path.suffix.lower() != ".pdf":
        raise CorruptedPDFError(f"O arquivo de entrada deve possuir extensão .pdf: {input_path}")

    try:
        if not input_path.exists():
            raise FileAccessError(f"Arquivo de entrada não encontrado: {input_path}")
        if not input_path.is_file():
            raise FileAccessError(f"O caminho de entrada não é um arquivo: {input_path}")
        if not os.access(input_path, os.R_OK):
            raise FileAccessError(f"Arquivo de entrada sem permissão de leitura: {input_path}")

        # Abrir o arquivo é uma verificação mais confiável que os.access() em
        # ambientes com ACLs, contêineres ou execução privilegiada.
        with input_path.open("rb") as source:
            header = source.read(_PDF_HEADER_LENGTH)
    except FileAccessError:
        raise
    except OSError as exc:
        raise FileAccessError(f"Não foi possível ler o arquivo de entrada: {input_path}") from exc

    if _PDF_SIGNATURE not in header:
        raise CorruptedPDFError(f"Assinatura PDF ausente ou inválida: {input_path}")


def _prepare_output(input_path: Path, output_path: Path) -> None:
    if output_path.suffix.lower() != ".pdf":
        raise FileAccessError(f"O arquivo de saída deve possuir extensão .pdf: {output_path}")

    try:
        if input_path.resolve() == output_path.resolve():
            raise FileAccessError("Os caminhos de entrada e saída devem ser diferentes.")

        output_directory = output_path.parent
        output_directory.mkdir(parents=True, exist_ok=True)
        if not output_directory.is_dir():
            raise FileAccessError(f"O diretório de destino não é um diretório: {output_directory}")
        if not os.access(output_directory, os.W_OK):
            raise FileAccessError(
                f"Diretório de destino sem permissão de escrita: {output_directory}"
            )
        if output_path.exists() and not output_path.is_file():
            raise FileAccessError(f"O caminho de saída não é um arquivo: {output_path}")
        if output_path.exists() and not os.access(output_path, os.W_OK):
            raise FileAccessError(f"Arquivo de saída sem permissão de escrita: {output_path}")
    except FileAccessError:
        raise
    except (OSError, ValueError) as exc:
        raise FileAccessError(f"Não foi possível preparar o destino: {output_path}") from exc


def _run_engine(
    input_path: Path,
    output_path: Path,
    languages: list[str],
    *,
    deskew: bool,
    clean: bool,
    skip_text: bool,
) -> int:
    exit_code = ocrmypdf.ocr(
        input_path,
        output_path,
        language=languages,
        deskew=deskew,
        clean=clean,
        skip_text=skip_text,
        progress_bar=False,
    )
    # OCRmyPDF devolve ExitCode (um IntEnum); a conversão mantém esta
    # fronteira independente do tipo interno exposto pela biblioteca.
    return int(exit_code)


def run_ocr(
    input_path: Path,
    output_path: Path,
    lang: str = "por",
    deskew: bool = True,
    clean: bool = True,
    skip_text: bool = True,
) -> Path:
    """Executa OCR em um PDF e devolve o caminho de saída.

    As falhas esperadas são expostas somente como exceções de domínio,
    permitindo que CLI, API HTTP ou jobs decidam como apresentá-las.
    """
    if not isinstance(input_path, Path) or not isinstance(output_path, Path):
        raise FileAccessError("input_path e output_path devem ser instâncias de pathlib.Path.")

    started_at = perf_counter()
    _log(
        logging.INFO,
        "ocr_started",
        input_path=input_path,
        output_path=output_path,
        started_at=started_at,
        status="started",
    )

    try:
        languages = _parse_languages(lang)
        _validate_input(input_path)
        _prepare_output(input_path, output_path)
        exit_code = _run_engine(
            input_path,
            output_path,
            languages,
            deskew=deskew,
            clean=clean,
            skip_text=skip_text,
        )
        if exit_code != 0:
            raise OCRProcessingError(f"OCRmyPDF terminou com código de saída {exit_code}.")
    except PriorOcrFoundError as exc:
        domain_error: OCRDomainError = OCRProcessingError(
            "O PDF já contém texto; use skip_text=True para ignorar essas páginas."
        )
        _log_failure(domain_error, input_path, output_path, started_at)
        raise domain_error from exc
    except (InputFileError, UnsupportedImageFormatError, DpiError, EncryptedPdfError) as exc:
        domain_error = CorruptedPDFError("O PDF está corrompido, criptografado ou não é suportado.")
        _log_failure(domain_error, input_path, output_path, started_at)
        raise domain_error from exc
    except OutputFileAccessError as exc:
        domain_error = FileAccessError(f"Não foi possível gravar o arquivo de saída: {output_path}")
        _log_failure(domain_error, input_path, output_path, started_at)
        raise domain_error from exc
    except (
        BadArgsError,
        MissingDependencyError,
        SubprocessOutputError,
        TesseractConfigError,
    ) as exc:
        domain_error = OCRProcessingError(f"Falha no motor OCR: {exc}")
        _log_failure(domain_error, input_path, output_path, started_at)
        raise domain_error from exc
    except OCRDomainError as exc:
        _log_failure(exc, input_path, output_path, started_at)
        raise
    except OSError as exc:
        domain_error = FileAccessError("Falha de acesso a arquivo durante o processamento OCR.")
        _log_failure(domain_error, input_path, output_path, started_at, exc_info=True)
        raise domain_error from exc
    except (TypeError, ValueError) as exc:
        domain_error = OCRProcessingError("O OCRmyPDF retornou um resultado inválido.")
        _log_failure(domain_error, input_path, output_path, started_at, exc_info=True)
        raise domain_error from exc
    except Exception as exc:
        domain_error = OCRProcessingError("Falha inesperada durante o processamento OCR.")
        _log_failure(domain_error, input_path, output_path, started_at, exc_info=True)
        raise domain_error from exc

    _log(
        logging.INFO,
        "ocr_completed",
        input_path=input_path,
        output_path=output_path,
        started_at=started_at,
        status="success",
    )
    return output_path


def _log_failure(
    error: OCRDomainError,
    input_path: Path,
    output_path: Path,
    started_at: float,
    *,
    exc_info: bool = False,
) -> None:
    _log(
        logging.ERROR,
        f"ocr_failed: {error}",
        input_path=input_path,
        output_path=output_path,
        started_at=started_at,
        status="error",
        exc_info=exc_info,
    )


__all__ = [
    "CorruptedPDFError",
    "FileAccessError",
    "OCRDomainError",
    "OCRProcessingError",
    "run_ocr",
]
