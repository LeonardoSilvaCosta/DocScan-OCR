"""Testes do contrato de domínio do pipeline OCR."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from ocrmypdf.exceptions import InputFileError, OutputFileAccessError, PriorOcrFoundError

from scanlayer.core.processor import (
    CorruptedPDFError,
    FileAccessError,
    OCRProcessingError,
    run_ocr,
)


def _pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.7\n")
    return path


def test_run_ocr_creates_destination_and_returns_path(tmp_path: Path) -> None:
    source = _pdf(tmp_path / "input.pdf")
    output = tmp_path / "nested" / "output.pdf"

    with patch("scanlayer.core.processor.ocrmypdf.ocr", return_value=0) as ocr:
        assert run_ocr(source, output) == output

    assert output.parent.is_dir()
    ocr.assert_called_once_with(
        source,
        output,
        language=["por"],
        deskew=True,
        clean=True,
        skip_text=True,
        progress_bar=False,
    )


@pytest.mark.parametrize("name", ["input.txt", "input"])
def test_run_ocr_rejects_non_pdf_extension(tmp_path: Path, name: str) -> None:
    source = tmp_path / name
    source.write_bytes(b"%PDF-1.7\n")
    with pytest.raises(CorruptedPDFError):
        run_ocr(source, tmp_path / "output.pdf")


def test_run_ocr_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(FileAccessError):
        run_ocr(tmp_path / "missing.pdf", tmp_path / "output.pdf")


@pytest.mark.parametrize(
    ("native_error", "domain_error"),
    [
        (InputFileError("bad pdf"), CorruptedPDFError),
        (OutputFileAccessError("denied"), FileAccessError),
        (PriorOcrFoundError("text"), OCRProcessingError),
    ],
)
def test_run_ocr_maps_native_errors(
    tmp_path: Path,
    native_error: Exception,
    domain_error: type[Exception],
) -> None:
    source = _pdf(tmp_path / "input.pdf")
    with (
        patch("scanlayer.core.processor.ocrmypdf.ocr", side_effect=native_error),
        pytest.raises(domain_error) as caught,
    ):
        run_ocr(source, tmp_path / "output.pdf")
    assert caught.value.__cause__ is native_error


def test_run_ocr_emits_structured_completion_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = _pdf(tmp_path / "input.pdf")
    with (
        caplog.at_level(logging.INFO, logger="scanlayer.core.processor"),
        patch("scanlayer.core.processor.ocrmypdf.ocr", return_value=0),
    ):
        run_ocr(source, tmp_path / "output.pdf")

    completed = next(record for record in caplog.records if record.msg == "ocr_completed")
    assert completed.input_file == "input.pdf"  # type: ignore[attr-defined]
    assert completed.status == "success"  # type: ignore[attr-defined]
    assert completed.elapsed_seconds >= 0  # type: ignore[attr-defined]
