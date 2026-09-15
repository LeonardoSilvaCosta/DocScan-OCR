"""Verifica validação e recuperação de falhas na fronteira de OCR."""

from pathlib import Path
from shutil import copyfile
from unittest.mock import patch

import pytest
from ocrmypdf.exceptions import InputFileError, PriorOcrFoundError, SubprocessOutputError
from pypdf import PdfReader

from scanlayer.processor import process_pdf


def _text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def test_synthetic_pdf_fixtures(rasterized_pdf: Path, digital_pdf: Path, sample_text: str) -> None:
    raster = PdfReader(rasterized_pdf)
    assert len(raster.pages) == 1
    assert len(raster.pages[0].images) == 1
    assert _text(rasterized_pdf).strip() == ""
    assert sample_text in _text(digital_pdf)


def test_success_contract_with_stubbed_engine(
    rasterized_pdf: Path, digital_pdf: Path, isolated_dir: Path, sample_text: str
) -> None:
    """Valida o contrato de saída; o reconhecimento real é testado na integração."""
    output = isolated_dir / "searchable.pdf"
    original = rasterized_pdf.read_bytes()

    def write_output(*_args: object, **_kwargs: object) -> int:
        copyfile(digital_pdf, output)
        return 0

    with patch("scanlayer.processor.ocrmypdf.ocr", side_effect=write_output) as ocr:
        assert process_pdf(rasterized_pdf, output)

    ocr.assert_called_once_with(
        rasterized_pdf,
        output,
        language=["por"],
        deskew=True,
        clean=True,
        skip_text=True,
        progress_bar=False,
    )
    assert sample_text in _text(output)
    assert rasterized_pdf.read_bytes() == original


@pytest.mark.parametrize("skip_text", [True, False])
def test_existing_text_contract(
    digital_pdf: Path, isolated_dir: Path, sample_text: str, skip_text: bool
) -> None:
    output = isolated_dir / "existing_text.pdf"
    original = digital_pdf.read_bytes()

    def existing_text_engine(*_args: object, **_kwargs: object) -> int:
        if not skip_text:
            raise PriorOcrFoundError("PDF already contains text")
        copyfile(digital_pdf, output)
        return 0

    with patch("scanlayer.processor.ocrmypdf.ocr", side_effect=existing_text_engine) as ocr:
        assert process_pdf(digital_pdf, output, skip_text=skip_text) is skip_text

    assert ocr.call_args.kwargs["skip_text"] is skip_text
    assert digital_pdf.read_bytes() == original
    if skip_text:
        assert _text(output).count(sample_text) == 1
    else:
        assert not output.exists()


@pytest.mark.integration
def test_rasterized_pdf_becomes_searchable_and_is_idempotent(
    rasterized_pdf: Path, isolated_dir: Path, sample_text: str
) -> None:
    """Exercita OCRmyPDF e Tesseract reais; falha se faltar infraestrutura."""
    output = isolated_dir / "ocr.pdf"
    repeated = isolated_dir / "ocr_again.pdf"
    original = rasterized_pdf.read_bytes()
    assert _text(rasterized_pdf).strip() == ""

    # Uma página, inglês e sem limpeza/deskew reduzem custo e dispensam unpaper.
    assert process_pdf(rasterized_pdf, output, lang="eng", deskew=False, clean=False)
    assert output.is_file()
    assert len(PdfReader(output).pages) == 1
    assert sample_text in " ".join(_text(output).split())
    assert rasterized_pdf.read_bytes() == original

    assert process_pdf(output, repeated, lang="eng", deskew=False, clean=False, skip_text=True)
    assert len(PdfReader(repeated).pages) == 1
    assert " ".join(_text(repeated).split()) == " ".join(_text(output).split())


@pytest.mark.integration
@pytest.mark.parametrize("skip_text", [True, False])
def test_digital_pdf_with_real_engine(
    digital_pdf: Path, isolated_dir: Path, sample_text: str, skip_text: bool
) -> None:
    output = isolated_dir / "digital_output.pdf"
    original = digital_pdf.read_bytes()
    assert (
        process_pdf(digital_pdf, output, lang="eng", deskew=False, clean=False, skip_text=skip_text)
        is skip_text
    )
    assert digital_pdf.read_bytes() == original
    if skip_text:
        assert len(PdfReader(output).pages) == 1
        assert _text(output).count(sample_text) == 1
    else:
        assert not output.exists()


def test_empty_input(isolated_dir: Path) -> None:
    source = isolated_dir / "empty.pdf"
    source.touch()
    output = isolated_dir / "out.pdf"
    with patch("scanlayer.processor.ocrmypdf.ocr") as ocr:
        assert not process_pdf(source, output)
    ocr.assert_not_called()
    assert source.stat().st_size == 0
    assert not output.exists()


@pytest.mark.parametrize("filename", ["input.txt", "input.png", "input"])
def test_invalid_extension(digital_pdf: Path, isolated_dir: Path, filename: str) -> None:
    # Conteúdo PDF válido: a rejeição deve ocorrer especificamente pela extensão.
    source = isolated_dir / filename
    copyfile(digital_pdf, source)
    output = isolated_dir / "out.pdf"
    with patch("scanlayer.processor.ocrmypdf.ocr") as ocr:
        assert not process_pdf(source, output)
    ocr.assert_not_called()
    assert not output.exists()


def test_missing_input(tmp_path: Path) -> None:
    with patch("scanlayer.processor.ocrmypdf.ocr") as ocr:
        assert not process_pdf(tmp_path / "missing.pdf", tmp_path / "out.pdf")
    ocr.assert_not_called()
    assert not (tmp_path / "out.pdf").exists()


def test_invalid_signature(tmp_path: Path) -> None:
    source = tmp_path / "invalid.pdf"
    source.write_bytes(b"not a PDF")
    with patch("scanlayer.processor.ocrmypdf.ocr") as ocr:
        assert not process_pdf(source, tmp_path / "out.pdf")
    ocr.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [InputFileError("corrupt"), PriorOcrFoundError("text"), MemoryError(), SubprocessOutputError()],
)
def test_engine_failure(tmp_path: Path, failure: Exception) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    with patch("scanlayer.processor.ocrmypdf.ocr", side_effect=failure):
        assert not process_pdf(source, tmp_path / "out.pdf")


def test_success_requires_output(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    with patch("scanlayer.processor.ocrmypdf.ocr", return_value=0):
        assert not process_pdf(source, tmp_path / "out.pdf")


def test_same_file_rejected(tmp_path: Path) -> None:
    source = tmp_path / "input.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    with patch("scanlayer.processor.ocrmypdf.ocr") as ocr:
        assert not process_pdf(source, source)
    ocr.assert_not_called()
