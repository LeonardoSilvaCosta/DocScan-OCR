"""Serviços centrais do ScanLayer."""

from scanlayer.core.processor import (
    CorruptedPDFError,
    FileAccessError,
    OCRProcessingError,
    run_ocr,
)

__all__ = [
    "CorruptedPDFError",
    "FileAccessError",
    "OCRProcessingError",
    "run_ocr",
]
