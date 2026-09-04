"""CLI utility to translate a Document model or digital PDF.

Usage:
    python scripts/translate_document.py input.json --target es --provider mock
    python scripts/translate_document.py doc.pdf --target es --output out.json
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.analyzers.document_analyzer import DocumentAnalyzer
from app.domain.models import Document
from app.translators.engine import TranslationEngine
from app.translators.factory import get_translator


async def run_translation(args: argparse.Namespace) -> int:
    """Execute document translation workflow."""
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Load Document either from analysis JSON or by analyzing PDF directly
    if input_path.suffix.lower() == ".pdf":
        print(f"Analyzing PDF '{input_path.name}'...")
        analyzer = DocumentAnalyzer()
        try:
            document = analyzer.analyze_file(input_path)
        except Exception as e:
            print(f"Error analyzing PDF: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Loading document model from '{input_path.name}'...")
        try:
            json_text = input_path.read_text(encoding="utf-8")
            document = Document.model_validate_json(json_text)
        except Exception as e:
            print(f"Error loading document JSON: {e}", file=sys.stderr)
            return 1

    # Select provider
    try:
        translator = get_translator(provider=args.provider)
    except Exception as e:
        print(f"Error initializing translator: {e}", file=sys.stderr)
        return 1

    print(
        f"Translating {document.page_count} page(s) to '{args.target}' "
        f"using provider '{args.provider}'..."
    )

    engine = TranslationEngine(translator=translator)
    try:
        translated_doc = await engine.translate_document(
            document=document,
            source_language=args.source,
            target_language=args.target,
            protected_terms=args.protected or [],
        )
    except Exception as e:
        print(f"Translation failed: {e}", file=sys.stderr)
        return 1

    total_translated = sum(
        sum(1 for b in p.blocks if b.translated_text) for p in translated_doc.pages
    )
    print("Translation completed successfully:")
    print(f"  Pages:              {translated_doc.page_count}")
    print(f"  Translated Blocks:  {total_translated}")

    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{input_path.stem}_translated.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        translated_doc.model_dump_json(indent=2),
        encoding="utf-8",
    )
    print(f"Translated JSON written to: {out_path}")
    return 0


def main() -> int:
    """Parse arguments and launch asynchronous translation runner."""
    parser = argparse.ArgumentParser(
        description=(
            "Translate a Document model or digital PDF using Tradux Translation Engine."
        )
    )
    parser.add_argument("input_file", type=str, help="Path to input JSON or PDF")
    parser.add_argument(
        "--target",
        "-t",
        type=str,
        default="es",
        help="Target language code (default: es)",
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Optional source language code (None = auto-detect)",
    )
    parser.add_argument(
        "--provider",
        "-p",
        type=str,
        default="mock",
        choices=["mock", "openai"],
        help="Translation provider (default: mock)",
    )
    parser.add_argument(
        "--protected",
        nargs="+",
        default=[],
        help="Protected terms that must not be translated",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to output JSON file",
    )

    args = parser.parse_args()
    return asyncio.run(run_translation(args))


if __name__ == "__main__":
    sys.exit(main())
