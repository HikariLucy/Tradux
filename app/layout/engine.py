"""LayoutEngine service for calculating text reflow, font scaling, and box expansion."""

import time

from app.domain.models import BoundingBox, Document, Page, TextBlock
from app.layout.config import LayoutConfig
from app.layout.fonts import resolve_font
from app.layout.measurement import TextMeasurer
from app.layout.models import (
    BlockLayout,
    DocumentLayout,
    LayoutStats,
    LayoutStatus,
    PageLayout,
)
from app.layout.styles import select_representative_style


class LayoutEngine:
    """Calculates typographic reflow and geometry for Document translations."""

    def __init__(self, config: LayoutConfig | None = None) -> None:
        """Initialize LayoutEngine with optional configuration thresholds."""
        self.config = config or LayoutConfig()

    def build(self, document: Document) -> DocumentLayout:
        """Calculate layout plans for all blocks in a document.

        Guarantees:
        - The input Document is never modified.
        - Text blocks without translated_text are marked SKIPPED and preserved.
        - Processing is deterministic, ordered by page_number and reading_order.
        - Returns an engine-agnostic DocumentLayout model.

        Args:
            document: Document domain model with translated_text.

        Returns:
            DocumentLayout with per-page BlockLayouts and aggregate statistics.
        """
        start_time = time.perf_counter()
        pages_layout: list[PageLayout] = []

        total_blocks = 0
        fit_count = 0
        shrunk_count = 0
        expanded_count = 0
        review_required_count = 0
        skipped_count = 0
        font_substitutions = 0

        # Sort pages sequentially by page_number
        sorted_pages = sorted(document.pages, key=lambda p: p.page_number)

        with TextMeasurer() as measurer:
            for page in sorted_pages:
                page_block_layouts: list[BlockLayout] = []
                # Sort blocks deterministically by reading_order
                sorted_blocks = sorted(page.blocks, key=lambda b: b.reading_order)

                for block in sorted_blocks:
                    total_blocks += 1
                    block_layout = self._layout_block(page, block, measurer)
                    page_block_layouts.append(block_layout)

                    # Update statistics
                    if block_layout.status == LayoutStatus.FIT:
                        fit_count += 1
                    elif block_layout.status == LayoutStatus.SHRUNK:
                        shrunk_count += 1
                    elif block_layout.status == LayoutStatus.EXPANDED:
                        expanded_count += 1
                    elif block_layout.status == LayoutStatus.REVIEW_REQUIRED:
                        review_required_count += 1
                    elif block_layout.status == LayoutStatus.SKIPPED:
                        skipped_count += 1

                    if block_layout.is_font_substituted:
                        font_substitutions += 1

                pages_layout.append(
                    PageLayout(
                        page_number=page.page_number,
                        blocks=page_block_layouts,
                    )
                )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        stats = LayoutStats(
            total_blocks=total_blocks,
            fit_count=fit_count,
            shrunk_count=shrunk_count,
            expanded_count=expanded_count,
            review_required_count=review_required_count,
            skipped_count=skipped_count,
            font_substitutions=font_substitutions,
        )

        metadata = {
            "duration_ms": round(duration_ms, 2),
            "page_count": len(pages_layout),
            "min_font_size": self.config.min_font_size,
            "min_font_scale": self.config.min_font_scale,
        }

        return DocumentLayout(
            pages=pages_layout,
            stats=stats,
            metadata=metadata,
        )

    def _layout_block(
        self,
        page: Page,
        block: TextBlock,
        measurer: TextMeasurer,
    ) -> BlockLayout:
        """Calculate layout for a single TextBlock."""
        # 1. Determine representative typography from source block
        rep_style = select_representative_style(block)
        resolved_font = resolve_font(
            rep_style.font_name,
            is_bold=rep_style.is_bold,
            is_italic=rep_style.is_italic,
        )

        orig_font_size = max(rep_style.font_size, 1.0)
        orig_bbox = block.bbox
        target_text = block.translated_text

        # 2. If translated_text is missing or empty, skip layout
        if target_text is None or not target_text.strip():
            warnings = ["Block skipped: no translation provided"]
            if resolved_font.is_substitution:
                warnings.append(
                    f"Font '{rep_style.font_name}' mapped to "
                    f"'{resolved_font.font_name}'"
                )
            return BlockLayout(
                page_number=page.page_number,
                reading_order=block.reading_order,
                bbox=orig_bbox,
                render_bbox=orig_bbox,
                text=block.text,
                original_font_name=rep_style.font_name,
                resolved_font_name=resolved_font.font_name,
                original_font_size=orig_font_size,
                final_font_size=orig_font_size,
                color=rep_style.color,
                line_height=self.config.default_line_height,
                status=LayoutStatus.SKIPPED,
                warnings=warnings,
                is_font_substituted=resolved_font.is_substitution,
            )

        # 3. Check for degenerated bbox
        if orig_bbox.width <= 0 or orig_bbox.height <= 0:
            return BlockLayout(
                page_number=page.page_number,
                reading_order=block.reading_order,
                bbox=orig_bbox,
                render_bbox=orig_bbox,
                text=target_text,
                original_font_name=rep_style.font_name,
                resolved_font_name=resolved_font.font_name,
                original_font_size=orig_font_size,
                final_font_size=orig_font_size,
                color=rep_style.color,
                line_height=self.config.default_line_height,
                status=LayoutStatus.REVIEW_REQUIRED,
                warnings=["Block bbox has non-positive width or height"],
                is_font_substituted=resolved_font.is_substitution,
            )

        warnings: list[str] = []
        if resolved_font.is_substitution:
            warnings.append(
                f"Font '{rep_style.font_name}' mapped to Base-14 "
                f"'{resolved_font.font_name}'"
            )

        # 4. Generate candidate line heights and font sizes
        def_lh = self.config.default_line_height
        min_lh = self.config.min_line_height
        lh_step = self.config.line_height_step

        line_heights: list[float] = [def_lh]
        curr_lh = def_lh - lh_step
        while curr_lh >= min_lh - 1e-4:
            line_heights.append(round(curr_lh, 2))
            curr_lh -= lh_step

        min_allowed_size = max(
            self.config.min_font_size,
            orig_font_size * self.config.min_font_scale,
        )

        font_sizes: list[float] = []
        curr_sz = orig_font_size - self.config.font_size_step
        while curr_sz >= min_allowed_size - 1e-4:
            font_sizes.append(round(curr_sz, 2))
            curr_sz -= self.config.font_size_step
        if not font_sizes and min_allowed_size < orig_font_size:
            font_sizes.append(round(min_allowed_size, 2))

        # -------------------------------------------------------------
        # Step A: Try original font size in original bbox
        # -------------------------------------------------------------
        for lh in line_heights:
            rc = measurer.measure(
                target_text,
                resolved_font.font_name,
                orig_font_size,
                orig_bbox.as_tuple(),
                lh,
            )
            if rc >= 0:
                return BlockLayout(
                    page_number=page.page_number,
                    reading_order=block.reading_order,
                    bbox=orig_bbox,
                    render_bbox=orig_bbox,
                    text=target_text,
                    original_font_name=rep_style.font_name,
                    resolved_font_name=resolved_font.font_name,
                    original_font_size=orig_font_size,
                    final_font_size=orig_font_size,
                    color=rep_style.color,
                    line_height=lh,
                    status=LayoutStatus.FIT,
                    warnings=warnings,
                    is_font_substituted=resolved_font.is_substitution,
                )

        # -------------------------------------------------------------
        # Step B: Try shrinking font size gradually in original bbox
        # -------------------------------------------------------------
        for sz in font_sizes:
            for lh in line_heights:
                rc = measurer.measure(
                    target_text,
                    resolved_font.font_name,
                    sz,
                    orig_bbox.as_tuple(),
                    lh,
                )
                if rc >= 0:
                    return BlockLayout(
                        page_number=page.page_number,
                        reading_order=block.reading_order,
                        bbox=orig_bbox,
                        render_bbox=orig_bbox,
                        text=target_text,
                        original_font_name=rep_style.font_name,
                        resolved_font_name=resolved_font.font_name,
                        original_font_size=orig_font_size,
                        final_font_size=sz,
                        color=rep_style.color,
                        line_height=lh,
                        status=LayoutStatus.SHRUNK,
                        warnings=warnings,
                        is_font_substituted=resolved_font.is_substitution,
                    )

        # -------------------------------------------------------------
        # Step C: Safe vertical expansion (if enabled)
        # -------------------------------------------------------------
        if self.config.allow_safe_vertical_expansion:
            clearance = self._calculate_vertical_clearance(page, block)
            max_allowed_exp = min(
                orig_bbox.height * self.config.max_vertical_expansion_ratio,
                self.config.max_vertical_expansion_pt,
            )
            usable_delta_y = min(max_allowed_exp, clearance)

            if usable_delta_y >= 2.0:
                expanded_bbox = BoundingBox(
                    x0=orig_bbox.x0,
                    y0=orig_bbox.y0,
                    x1=orig_bbox.x1,
                    y1=orig_bbox.y1 + usable_delta_y,
                )

                candidate_sizes = [orig_font_size] + font_sizes
                for sz in candidate_sizes:
                    for lh in line_heights:
                        rc = measurer.measure(
                            target_text,
                            resolved_font.font_name,
                            sz,
                            expanded_bbox.as_tuple(),
                            lh,
                        )
                        if rc >= 0:
                            return BlockLayout(
                                page_number=page.page_number,
                                reading_order=block.reading_order,
                                bbox=orig_bbox,
                                render_bbox=expanded_bbox,
                                text=target_text,
                                original_font_name=rep_style.font_name,
                                resolved_font_name=resolved_font.font_name,
                                original_font_size=orig_font_size,
                                final_font_size=sz,
                                color=rep_style.color,
                                line_height=lh,
                                status=LayoutStatus.EXPANDED,
                                warnings=warnings,
                                is_font_substituted=resolved_font.is_substitution,
                            )

        # -------------------------------------------------------------
        # Step D: Overflow -> REVIEW_REQUIRED
        # -------------------------------------------------------------
        deficit_pt = abs(rc)
        warnings.append(
            f"Text does not fit legibility limits (height deficit: {deficit_pt:.1f}pt)"
        )

        return BlockLayout(
            page_number=page.page_number,
            reading_order=block.reading_order,
            bbox=orig_bbox,
            render_bbox=orig_bbox,
            text=target_text,
            original_font_name=rep_style.font_name,
            resolved_font_name=resolved_font.font_name,
            original_font_size=orig_font_size,
            final_font_size=min_allowed_size,
            color=rep_style.color,
            line_height=min_lh,
            status=LayoutStatus.REVIEW_REQUIRED,
            warnings=warnings,
            is_font_substituted=resolved_font.is_substitution,
        )

    def _calculate_vertical_clearance(self, page: Page, block: TextBlock) -> float:
        """Calculate available vertical distance below block without colliding."""
        bbox = block.bbox
        # 1. Clearance to bottom of page
        page_bottom_limit = page.height - self.config.page_margin_pt
        if bbox.y1 >= page_bottom_limit:
            return 0.0
        clearance = page_bottom_limit - bbox.y1

        # 2. Check collision against other text blocks on the page
        tol = self.config.geometric_tolerance_pt
        for other_b in page.blocks:
            if other_b.reading_order == block.reading_order:
                continue
            # Check horizontal overlap
            x_overlaps = not (other_b.bbox.x1 <= bbox.x0 or other_b.bbox.x0 >= bbox.x1)
            if x_overlaps and other_b.bbox.y0 >= bbox.y1:
                dist = max(0.0, other_b.bbox.y0 - bbox.y1 - tol)
                clearance = min(clearance, dist)

        # 3. Check collision against image elements on the page
        for img in page.images:
            if img.bbox is not None:
                x_overlaps = not (img.bbox.x1 <= bbox.x0 or img.bbox.x0 >= bbox.x1)
                if x_overlaps and img.bbox.y0 >= bbox.y1:
                    dist = max(0.0, img.bbox.y0 - bbox.y1 - tol)
                    clearance = min(clearance, dist)

        return max(0.0, clearance)
