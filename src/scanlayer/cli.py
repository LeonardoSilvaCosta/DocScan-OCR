"""Interface de linha de comando do ScanLayer."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from scanlayer.core.processor import OCRDomainError, run_ocr
from scanlayer.processor import process_pdf

app = typer.Typer(
    help="Adiciona uma camada OCR a um PDF ou a um diretório de PDFs.",
    add_completion=False,
    context_settings={"allow_extra_args": True},
)
console = Console(stderr=True)

Status = Literal["sucesso", "pulado", "falha"]
_LANGUAGE_CODE = re.compile(r"^[A-Za-z0-9_/-]+$")


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Resultado apresentável de um arquivo do lote."""

    source: Path
    status: Status
    reason: str = ""


def _argument_error(message: str, parameter: str) -> typer.BadParameter:
    return typer.BadParameter(message, param_hint=parameter)


def _resolve_invocation(
    ctx: typer.Context, input_path: Path | None, output_path: Path | None
) -> tuple[Path, Path | None, bool]:
    """Resolve as flags atuais e aceita a sintaxe posicional antiga em transição."""
    legacy_args = ctx.args
    if input_path is not None and legacy_args:
        raise _argument_error("não combine --input com argumentos posicionais", "--input")
    if len(legacy_args) > 2:
        raise _argument_error("argumentos posicionais em excesso", "--input")

    legacy_mode = input_path is None and bool(legacy_args)
    if legacy_mode:
        input_path = Path(legacy_args[0])
        if len(legacy_args) == 2:
            if output_path is not None:
                raise _argument_error("a saída foi informada duas vezes", "--output")
            output_path = Path(legacy_args[1])

    if input_path is None:
        raise _argument_error("a opção é obrigatória", "--input / -i")
    return input_path, output_path, legacy_mode


def _discover_pdfs(input_path: Path) -> tuple[list[Path], bool]:
    try:
        if not input_path.exists():
            raise _argument_error(f"caminho não encontrado: {input_path}", "--input")
        if input_path.is_file():
            if input_path.suffix.lower() != ".pdf":
                raise _argument_error("o arquivo de entrada deve ter extensão .pdf", "--input")
            return [input_path], False
        if not input_path.is_dir():
            raise _argument_error("o caminho deve ser um arquivo ou diretório", "--input")

        pdfs = sorted(
            (
                path
                for path in input_path.rglob("*")
                if path.is_file() and path.suffix.lower() == ".pdf"
            ),
            key=lambda path: str(path).casefold(),
        )
    except typer.BadParameter:
        raise
    except OSError as exc:
        raise _argument_error(f"não foi possível ler o caminho: {exc}", "--input") from exc

    if not pdfs:
        raise _argument_error("nenhum arquivo PDF foi encontrado no diretório", "--input")
    return pdfs, True


def _output_for(
    source: Path,
    *,
    input_root: Path,
    output_path: Path | None,
    batch: bool,
) -> Path:
    generated_name = f"{source.stem}_ocr.pdf"
    if output_path is None:
        return source.with_name(generated_name)
    if not batch:
        if output_path.exists() and output_path.is_dir():
            return output_path / generated_name
        return output_path

    relative_parent = source.relative_to(input_root).parent
    return output_path / relative_parent / generated_name


def _validate_output(input_path: Path, output_path: Path | None, *, batch: bool) -> None:
    if output_path is None:
        return
    if batch:
        if output_path.exists() and not output_path.is_dir():
            raise _argument_error("a saída de um lote deve ser um diretório", "--output")
        if not output_path.exists() and output_path.suffix.lower() == ".pdf":
            raise _argument_error("a saída de um lote deve ser um diretório", "--output")
        return
    if not (output_path.exists() and output_path.is_dir()) and output_path.suffix.lower() != ".pdf":
        raise _argument_error("a saída deve ser um arquivo .pdf ou diretório", "--output")
    if (
        output_path.exists()
        and output_path.is_file()
        and input_path.resolve() == output_path.resolve()
    ):
        raise _argument_error("entrada e saída devem ser diferentes", "--output")


def _format_reasons(results: list[ProcessingResult], status: Status) -> str:
    matching = [result for result in results if result.status == status]
    if not matching:
        return "—"
    return "\n".join(f"{result.source.name}: {result.reason}" for result in matching)


def _print_summary(results: list[ProcessingResult]) -> None:
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("sucesso", "pulado", "falha")
    }
    table = Table(title="Resumo do processamento", show_header=True, header_style="bold cyan")
    table.add_column("Resultado", style="bold")
    table.add_column("Quantidade", justify="right")
    table.add_column("Motivos")
    table.add_row("Total", str(len(results)), "—")
    table.add_row("Sucessos", str(counts["sucesso"]), "—", style="green")
    table.add_row(
        "Pulados", str(counts["pulado"]), _format_reasons(results, "pulado"), style="yellow"
    )
    table.add_row("Falhas", str(counts["falha"]), _format_reasons(results, "falha"), style="red")
    console.print(table)


def _run_one(
    source: Path,
    destination: Path,
    *,
    lang: str,
    deskew: bool,
    clean: bool,
    skip_text: bool,
    legacy_mode: bool,
) -> ProcessingResult:
    if destination.exists():
        return ProcessingResult(source, "pulado", f"a saída já existe: {destination}")

    try:
        # A sintaxe posicional permanece compatível por uma versão. O fluxo
        # por flags usa a API de domínio, que preserva o motivo exato da falha.
        if legacy_mode:
            succeeded = process_pdf(source, destination, lang, deskew, clean, skip_text)
            if not succeeded:
                return ProcessingResult(source, "falha", "o pipeline OCR não foi concluído")
        else:
            run_ocr(source, destination, lang, deskew, clean, skip_text)
    except OCRDomainError as exc:
        return ProcessingResult(source, "falha", str(exc))
    except Exception as exc:  # Mantém o restante do lote em execução.
        logging.getLogger(__name__).exception("Falha inesperada ao processar %s", source)
        return ProcessingResult(source, "falha", f"erro inesperado: {exc}")
    return ProcessingResult(source, "sucesso")


@app.command()
def process(
    ctx: typer.Context,
    input_path: Annotated[
        Path | None,
        typer.Option("--input", "-i", help="Arquivo PDF ou diretório de entrada."),
    ] = None,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Arquivo ou diretório de saída."),
    ] = None,
    lang: Annotated[str, typer.Option("--lang", help="Idiomas, como por+eng.")] = "por",
    deskew: Annotated[
        bool,
        typer.Option("--deskew/--no-deskew", help="Corrigir inclinação."),
    ] = True,
    clean: Annotated[
        bool,
        typer.Option("--clean/--no-clean", help="Limpar ruído usando unpaper."),
    ] = True,
    skip_text: Annotated[
        bool,
        typer.Option(
            "--skip-text/--force-ocr",
            help="Pular páginas com texto ou forçar OCR em todas.",
        ),
    ] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Processa um PDF ou, recursivamente, todos os PDFs de um diretório."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
        handlers=[RichHandler(console=console, markup=False, show_path=verbose)],
        force=True,
    )

    input_path, output_path, legacy_mode = _resolve_invocation(ctx, input_path, output_path)
    languages = [code.strip() for code in lang.split("+") if code.strip()]
    if not languages or any(_LANGUAGE_CODE.fullmatch(code) is None for code in languages):
        raise _argument_error(f"código de idioma inválido: {lang!r}", "--lang")
    # O modo legado delega a validação ao processador antigo. Isso também
    # preserva o contrato de integrações que substituem essa fronteira em testes.
    if legacy_mode:
        sources, batch = [input_path], False
    else:
        sources, batch = _discover_pdfs(input_path)
    _validate_output(input_path, output_path, batch=batch)

    results: list[ProcessingResult] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )
    with progress:
        task = progress.add_task("Preparando...", total=len(sources))
        for source in sources:
            progress.update(task, description=f"[cyan]{source.name}[/cyan]")
            destination = _output_for(
                source,
                input_root=input_path,
                output_path=output_path,
                batch=batch,
            )
            if batch and source.stem.casefold().endswith("_ocr"):
                result = ProcessingResult(source, "pulado", "aparenta ser uma saída OCR")
            else:
                result = _run_one(
                    source,
                    destination,
                    lang=lang,
                    deskew=deskew,
                    clean=clean,
                    skip_text=skip_text,
                    legacy_mode=legacy_mode,
                )
            results.append(result)
            progress.advance(task)

    _print_summary(results)
    if any(result.status == "falha" for result in results):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
