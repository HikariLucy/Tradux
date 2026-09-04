"""CLI script to analyze any local PDF document and generate structured JSON.

Usage:
    python scripts/analyze_document.py input.pdf [--output output/analysis.json]
"""

import argparse
import sys
from pathlib import Path

from app.analyzers.document_analyzer import DocumentAnalyzer


def main() -> int:
    """Parse CLI arguments and run document analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze a PDF document and export structured JSON model."
    )
    parser.add_argument("pdf_file", type=str, help="Path to the PDF file to analyze")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional path to output JSON file (default: output/<stem>_analysis.json)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2)",
    )

    args = parser.parse_args()
    pdf_path = Path(args.pdf_file)

    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        return 1

    print(f"Analyzing '{pdf_path.name}'...")
    analyzer = DocumentAnalyzer()
    try:
        doc = analyzer.analyze_file(pdf_path)
    except Exception as e:
        print(f"Error analyzing document: {e}", file=sys.stderr)
        return 1

    total_blocks = sum(len(p.blocks) for p in doc.pages)
    total_lines = sum(sum(len(b.lines) for b in p.blocks) for p in doc.pages)
    total_spans = sum(
        sum(sum(len(line.spans) for line in b.lines) for b in p.blocks)
        for p in doc.pages
    )
    total_images = sum(len(p.images) for p in doc.pages)

    print("Analysis completed successfully:")
    print(f"  Pages:        {doc.page_count}")
    print(f"  Text Blocks:  {total_blocks}")
    print(f"  Lines:        {total_lines}")
    print(f"  Text Spans:   {total_spans}")
    print(f"  Images:       {total_images}")

    json_data = doc.model_dump_json(indent=args.indent)

    if args.output:
        out_path = Path(args.output)
    else:
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{pdf_path.stem}_analysis.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json_data, encoding="utf-8")
    print(f"JSON export written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
