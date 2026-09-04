"""Service orchestrating document analysis, translation, layout, and reconstruction."""

import asyncio
import logging
from typing import Any

from app.analyzers import DocumentAnalyzer
from app.core.config import Settings, get_settings
from app.core.errors import TraduxError
from app.jobs.models import Job, JobLayoutStats, JobMode, JobStatus
from app.jobs.store import JobStore, get_job_store
from app.layout import LayoutEngine
from app.renderers import PyMuPDFRenderer
from app.translators.engine import TranslationEngine
from app.translators.factory import get_translator
from app.translators.mock import MockTranslator

logger = logging.getLogger(__name__)


class ProviderNotConfiguredError(TraduxError):
    """Raised when configured translation mode lacks valid server credentials."""


def check_configured_provider_available(settings: Settings) -> tuple[bool, str]:
    """Determine if a real translation provider is properly configured.

    Returns:
        tuple[bool, str]: (is_available, provider_name)
    """
    provider = settings.translation_provider.strip().lower()
    if provider in ("openai", "chatgpt"):
        key = settings.translation_api_key
        key_str = (
            key.get_secret_value()
            if hasattr(key, "get_secret_value")
            else str(key or "")
        )
        has_key = bool(key_str.strip())
        return has_key, "openai"
    if provider == "mock":
        return False, "mock"
    return False, provider


class TranslationJobService:
    """Orchestrator for translation jobs, running pipeline stages sequentially."""

    def __init__(
        self,
        store: JobStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store or get_job_store()
        self.settings = settings or get_settings()
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def create_job(
        self,
        filename: str,
        source_pdf: bytes,
        target_language: str,
        source_language: str | None = None,
        mode: JobMode = JobMode.DEMO,
        protected_terms: list[str] | None = None,
    ) -> Job:
        """Create and store a new translation job, validating mode configuration."""
        if mode == JobMode.CONFIGURED:
            available, provider_name = check_configured_provider_available(
                self.settings
            )
            if not available:
                raise ProviderNotConfiguredError(
                    f"Configured translation provider '{provider_name}' is not "
                    "available or missing credentials on server"
                )
            logical_provider = provider_name
        else:
            logical_provider = "mock"

        active_count = self.store.active_count()
        if active_count >= self.settings.job_max_active:
            raise TraduxError(
                "Maximum number of active translation jobs reached. "
                "Please retry in a moment."
            )

        job = Job(
            filename=filename,
            source_language=source_language,
            target_language=target_language,
            mode=mode,
            provider=logical_provider,
            protected_terms=protected_terms or [],
            status=JobStatus.CREATED,
            stage="created",
            stage_message="Trabajo recibido",
        )
        self.store.add(job, source_pdf)
        return job

    def start_job(self, job_id: str) -> asyncio.Task[None]:
        """Launch background in-process execution of the job."""
        task = asyncio.create_task(self.run_job(job_id))
        self._tasks[job_id] = task

        def _cleanup(t: asyncio.Task[None]) -> None:
            self._tasks.pop(job_id, None)

        task.add_done_callback(_cleanup)
        return task

    async def run_job(self, job_id: str) -> None:
        """Execute the translation job pipeline through all stages."""
        job = self.store.get(job_id)
        if job is None:
            logger.warning("Attempted to run unknown or expired job %s", job_id)
            return

        source_pdf = self.store.get_source_pdf(job_id)
        if not source_pdf:
            self.store.update(
                job_id,
                status=JobStatus.FAILED,
                stage="failed",
                stage_message="Archivo PDF fuente no encontrado en memoria",
                error_code="MissingSourcePDF",
                error_message="Archivo PDF fuente no encontrado",
            )
            return

        stage = "analyzing"
        try:
            # 1. Document Analysis
            self.store.update(
                job_id,
                status=JobStatus.ANALYZING,
                stage="analyzing",
                stage_message="Analizando documento",
            )
            analyzer = DocumentAnalyzer()
            # Analyze synchronously (runs fast in memory)
            document = await asyncio.to_thread(
                analyzer.analyze_bytes, source_pdf, job.filename
            )
            total_blocks = sum(len(page.blocks) for page in document.pages)
            self.store.update(
                job_id,
                page_count=document.page_count,
                total_blocks=total_blocks,
            )

            # 2. Translation
            stage = "translating"
            self.store.update(
                job_id,
                status=JobStatus.TRANSLATING,
                stage="translating",
                stage_message="Traduciendo bloques",
            )
            if job.mode == JobMode.CONFIGURED:
                translator = get_translator(settings=self.settings)
            else:
                translator = MockTranslator()

            engine = TranslationEngine(translator=translator)
            translated_doc = await engine.translate_document(
                document=document,
                source_language=job.source_language,
                target_language=job.target_language,
                protected_terms=job.protected_terms,
            )

            translated_blocks = sum(
                1
                for page in translated_doc.pages
                for block in page.blocks
                if block.translated_text is not None
            )
            detected_lang = getattr(engine, "detected_source_language", None)
            self.store.update(
                job_id,
                translated_blocks=translated_blocks,
                detected_source_language=detected_lang or job.source_language,
            )

            # 3. Layout Calculation
            stage = "layout"
            self.store.update(
                job_id,
                status=JobStatus.LAYOUT,
                stage="layout",
                stage_message="Calculando layout",
            )
            layout_engine = LayoutEngine()
            layout = await asyncio.to_thread(layout_engine.build, translated_doc)
            layout_stats = JobLayoutStats(
                fit_count=layout.stats.fit_count,
                shrunk_count=layout.stats.shrunk_count,
                expanded_count=layout.stats.expanded_count,
                review_required_count=layout.stats.review_required_count,
            )
            self.store.update(
                job_id,
                layout_stats=layout_stats,
            )

            # 4. PDF Reconstruction / Rendering
            stage = "rendering"
            self.store.update(
                job_id,
                status=JobStatus.RENDERING,
                stage="rendering",
                stage_message="Reconstruyendo PDF",
            )
            renderer = PyMuPDFRenderer()
            result = await asyncio.to_thread(
                renderer.render,
                source_pdf=source_pdf,
                document=translated_doc,
                layout=layout,
            )
            self.store.save_result(job_id, result.pdf_bytes)

            # 5. Completed
            stage = "completed"
            self.store.update(
                job_id,
                status=JobStatus.COMPLETED,
                stage="completed",
                stage_message="Completado",
                result_available=True,
            )
            logger.info("Translation job %s completed successfully", job_id)

        except Exception as e:
            # Strictly sanitized logging: only exception class name and stage.
            # Never log raw exception text, document text, or secrets!
            logger.error(
                "Job %s failed in stage %s with exception: %s",
                job_id,
                stage,
                type(e).__name__,
            )
            self.store.update(
                job_id,
                status=JobStatus.FAILED,
                stage="failed",
                stage_message="Error en el procesamiento del documento",
                error_code=type(e).__name__,
                error_message="Error en el procesamiento del documento",
            )


_global_job_service: TranslationJobService | None = None


def get_job_service() -> TranslationJobService:
    """Return singleton TranslationJobService instance."""
    global _global_job_service
    if _global_job_service is None:
        _global_job_service = TranslationJobService()
    return _global_job_service
