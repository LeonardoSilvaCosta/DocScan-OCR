"""PDFs sintéticos e isolamento dos testes, sem documentos externos."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-ocr",
        action="store_true",
        default=False,
        help="Executa também a integração com Tesseract e Ghostscript reais.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-ocr"):
        return
    skip = pytest.mark.skip(reason="OCR real: execute pytest --run-ocr")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def isolated_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cada teste trabalha em seu próprio diretório, restaurado pelo pytest."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def sample_text() -> str:
    return "SCANLAYER TEST DOCUMENT 12345"


@pytest.fixture
def rasterized_pdf(isolated_dir: Path, sample_text: str) -> Path:
    """Uma página de imagem a 150 DPI, sem operadores de texto no PDF."""
    path = isolated_dir / "rasterized.pdf"
    with Image.new("RGB", (1500, 500), "white") as page:
        draw = ImageDraw.Draw(page)
        # A fonte incluída no Pillow evita depender de fontes do sistema.
        font = ImageFont.load_default(size=56)
        draw.text((80, 180), sample_text, font=font, fill="black")
        page.save(path, "PDF", resolution=150.0)
    return path


@pytest.fixture
def digital_pdf(isolated_dir: Path, sample_text: str) -> Path:
    """PDF digital usando a fonte padrão Helvetica, sem dependências de fontes."""
    path = isolated_dir / "digital.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=720, height=240)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    content = DecodedStreamObject()
    content.set_data(f"BT /F1 24 Tf 40 120 Td ({sample_text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = content
    writer.write(path)
    return path
