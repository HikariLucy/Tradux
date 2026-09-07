"""In-memory ephemeral store for translation jobs and binary artifacts."""

import logging
import threading
from datetime import UTC, datetime

from app.core.config import get_settings
from app.jobs.models import Job

logger = logging.getLogger(__name__)


class JobStore:
    """Thread-safe in-memory ephemeral store for jobs and PDF buffers.

    Note:
        This store is strictly in-process and non-durable. Restarting FastAPI
        resets all jobs and buffered PDFs.
    """

    def __init__(
        self,
        ttl_seconds: int | None = None,
        max_retained_jobs: int | None = None,
    ) -> None:
        settings = get_settings()
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else settings.job_ttl_seconds
        )
        self.max_retained_jobs = (
            max_retained_jobs
            if max_retained_jobs is not None
            else settings.job_max_retained
        )
        self._jobs: dict[str, Job] = {}
        self._source_pdfs: dict[str, bytes] = {}
        self._result_pdfs: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def add(self, job: Job, source_pdf: bytes) -> None:
        """Register a new job and buffer its source PDF."""
        with self._lock:
            self._cleanup_expired_locked()
            self._enforce_capacity_locked()
            self._jobs[job.job_id] = job
            self._source_pdfs[job.job_id] = source_pdf

    def get(self, job_id: str) -> Job | None:
        """Retrieve a job by ID, returning None if not found or expired."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if self._is_expired_locked(job):
                self._delete_locked(job_id)
                return None
            return job.model_copy()

    def update(self, job_id: str, **kwargs: object) -> Job | None:
        """Update job fields safely under lock."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, val in kwargs.items():
                if hasattr(job, key):
                    setattr(job, key, val)
            job.updated_at = datetime.now(UTC)
            return job.model_copy()

    def get_source_pdf(self, job_id: str) -> bytes | None:
        """Retrieve the buffered source PDF bytes for a job."""
        with self._lock:
            return self._source_pdfs.get(job_id)

    def save_result(self, job_id: str, result_pdf: bytes) -> None:
        """Save the reconstructed result PDF bytes."""
        with self._lock:
            self._result_pdfs[job_id] = result_pdf
            job = self._jobs.get(job_id)
            if job is not None:
                job.result_available = True
                job.updated_at = datetime.now(UTC)

    def get_result(self, job_id: str) -> bytes | None:
        """Retrieve the reconstructed result PDF bytes."""
        with self._lock:
            return self._result_pdfs.get(job_id)

    def delete(self, job_id: str, force: bool = False) -> bool:
        """Explicitly delete a job and release its in-memory buffers.

        Active jobs are protected and cannot be deleted unless force=True.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job and not job.status.is_terminal and not force:
                return False
            return self._delete_locked(job_id)

    def cleanup_expired(self) -> int:
        """Remove jobs that have exceeded TTL."""
        with self._lock:
            return self._cleanup_expired_locked()

    def active_count(self) -> int:
        """Count jobs currently in non-terminal states."""
        with self._lock:
            return sum(1 for j in self._jobs.values() if not j.status.is_terminal)

    def total_count(self) -> int:
        """Total number of retained jobs."""
        with self._lock:
            return len(self._jobs)

    def clear(self) -> None:
        """Reset the store completely (primarily for testing)."""
        with self._lock:
            self._jobs.clear()
            self._source_pdfs.clear()
            self._result_pdfs.clear()

    # Private internal helpers (must be called with self._lock held)

    def _is_expired_locked(self, job: Job) -> bool:
        if not job.status.is_terminal:
            return False
        age = (datetime.now(UTC) - job.created_at).total_seconds()
        return age > self.ttl_seconds

    def _delete_locked(self, job_id: str) -> bool:
        found = job_id in self._jobs
        self._jobs.pop(job_id, None)
        self._source_pdfs.pop(job_id, None)
        self._result_pdfs.pop(job_id, None)
        return found

    def _cleanup_expired_locked(self) -> int:
        now = datetime.now(UTC)
        # Active jobs are NEVER expired or purged while running!
        expired_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status.is_terminal
            and (now - job.created_at).total_seconds() > self.ttl_seconds
        ]
        for job_id in expired_ids:
            self._delete_locked(job_id)
        if expired_ids:
            logger.info("Cleaned up %d expired translation jobs", len(expired_ids))
        return len(expired_ids)

    def _enforce_capacity_locked(self) -> None:
        if len(self._jobs) < self.max_retained_jobs:
            return
        # Prioritize pruning oldest completed or failed jobs first
        terminal_jobs = [
            (job.created_at, job_id)
            for job_id, job in self._jobs.items()
            if job.status.is_terminal
        ]
        terminal_jobs.sort()
        while len(self._jobs) >= self.max_retained_jobs and terminal_jobs:
            _, oldest_id = terminal_jobs.pop(0)
            self._delete_locked(oldest_id)


_global_job_store: JobStore | None = None


def get_job_store() -> JobStore:
    """Return singleton JobStore instance."""
    global _global_job_store
    if _global_job_store is None:
        _global_job_store = JobStore()
    return _global_job_store
