"""Contratos públicos da CLI sem invocar executáveis de OCR."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from scanlayer.cli import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--lang" in result.output


def test_cli_options() -> None:
    with patch("scanlayer.cli.process_pdf", return_value=True) as process:
        result = runner.invoke(app, ["in.pdf", "out.pdf", "--lang", "por+eng", "--no-clean"])
    assert result.exit_code == 0
    process.assert_called_once_with(Path("in.pdf"), Path("out.pdf"), "por+eng", True, False, True)


def test_processing_failure() -> None:
    with patch("scanlayer.cli.process_pdf", return_value=False):
        result = runner.invoke(app, ["in.pdf", "out.pdf"])
    assert result.exit_code == 1


def test_missing_arguments() -> None:
    assert runner.invoke(app, []).exit_code == 2
