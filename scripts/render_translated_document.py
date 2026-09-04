"""CLI utility to render a reconstructed translated PDF from a Document model.

Usage:
    python scripts/render_translated_document.py source.pdf doc.json
    python scripts/render_translated_document.py source.pdf doc.json -o out.pdf
"""

import argparse
import sys
import time
from pathlib import Path

from app.domain.models import Document
from app.layout.config import LayoutConfig
from app.layout.engine import LayoutEngine
from app.renderers.pymupdf_renderer import PyMuPDFRenderer


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for PDF rendering."""
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct a translated digital PDF using "
            "LayoutEngine and PyMuPDFRenderer."
        ),
    )
    parser.add_argument(
        "source_pdf",
        type=str,
        help="Path to the original source PDF file",
    )
    parser.add_argument(
        "translated_model",
        type=str,
        help="Path to the translated Document JSON file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="output/tradux-rendered.pdf",
        help="Output rendered PDF path (default: output/tradux-rendered.pdf)",
    )
    parser.add_argument(
        "--layout-report",
        type=str,
        default=None,
        help="Optional path to write the DocumentLayout JSON report",
    )
    parser.add_argument(
        "--min-font-size",
        type=float,
        default=7.0,
        help="Absolute minimum font size in points (default: 7.0)",
    )
    parser.add_argument(
        "--min-font-scale",
        type=float,
        default=0.75,
        help="Minimum font scale factor relative to original size (default: 0.75)",
    )
    return parser.parse_args()


def main() -> int:
    """Execute PDF rendering workflow."""
    args = parse_args()

    source_path = Path(args.source_pdf).resolve()
    if not source_path.exists() or not source_path.is_file():
        print(f"Error: Source PDF not found: {source_path}", file=sys.stderr)
        return 1

    model_path = Path(args.translated_model).resolve()
    if not model_path.exists() or not model_path.is_file():
        print(f"Error: Translated model JSON not found: {model_path}", file=sys.stderr)
        return 1

    print(f"Loading translated Document model from '{model_path.name}'...")
    try:
        json_content = model_path.read_text(encoding="utf-8")
        document = Document.model_validate_json(json_content)
    except Exception as e:
        print(f"Error validating Document JSON: {e}", file=sys.stderr)
        return 1

    print(
        f"Document loaded: {document.page_count} page(s), "
        f"{sum(len(p.blocks) for p in document.pages)} total block(s)."
    )

    # 1. Build layout plan
    print("Calculating layout adjustment and line reflow...")
    t_layout_start = time.perf_counter()
    config = LayoutConfig(
        min_font_size=args.min_font_size,
        min_font_scale=args.min_font_scale,
    )
    engine = LayoutEngine(config=config)
    try:
        layout = engine.build(document)
    except Exception as e:
        print(f"Layout calculation failed: {e}", file=sys.stderr)
        return 1
    layout_time_ms = (time.perf_counter() - t_layout_start) * 1000.0

    print(
        f"Layout complete in {layout_time_ms:.1f}ms: "
        f"{layout.stats.fit_count} fit, "
        f"{layout.stats.shrunk_count} shrunk, "
        f"{layout.stats.expanded_count} expanded, "
        f"{layout.stats.review_required_count} review required, "
        f"{layout.stats.skipped_count} skipped, "
        f"{layout.stats.font_substitutions} font substitutions."
    )

    # 2. Write layout report if requested
    if args.layout_report:
        report_path = Path(args.layout_report).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(layout.to_json(indent=2), encoding="utf-8")
        print(f"Layout report written to '{report_path}'.")

    # 3. Render PDF
    print(f"Rendering PDF using source '{source_path.name}'...")
    t_render_start = time.perf_counter()
    renderer = PyMuPDFRenderer()
    try:
        result = renderer.render(
            source_pdf=source_path,
            document=document,
            layout=layout,
        )
    except Exception as e:
        print(f"PDF rendering failed: {e}", file=sys.stderr)
        return 1
    render_time_ms = (time.perf_counter() - t_render_start) * 1000.0

    # 4. Save output
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result.pdf_bytes)

    source_size = source_path.stat().st_size
    output_size = len(result.pdf_bytes)

    print(f"\nSuccessfully generated '{output_path.name}':")
    print(f"- Destination: {output_path}")
    print(f"- Pages rendered: {result.page_count}")
    print(f"- Blocks rendered: {result.rendered_blocks}")
    print(f"- Blocks skipped: {result.skipped_blocks}")
    print(f"- Blocks review required: {result.review_required_blocks}")
    print(f"- Font substitutions: {result.font_substitutions}")
    print(f"- Source size: {source_size:,} bytes")
    print(f"- Output size: {output_size:,} bytes")
    print(f"- Layout time: {layout_time_ms:.1f}ms")
    print(f"- Render time: {render_time_ms:.1f}ms")

    if result.warnings:
        print(f"- Warnings ({len(result.warnings)}):")
        for w in result.warnings[:5]:
            print(f"  * {w}")
        if len(result.warnings) > 5:
            print(f"  * ... and {len(result.warnings) - 5} more warnings.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
