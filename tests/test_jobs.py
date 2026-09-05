"""Comprehensive offline tests for translation jobs and store (Phase 4 MVP)."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import pymupdf
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.jobs.models import (
    Job,
    JobLayoutStats,
    JobMode,
    JobResponse,
    JobStatus,
)
from app.jobs.service import (
    TranslationJobService,
)
from app.jobs.store import JobStore, get_job_store
from app.main import app
from app.translators.base import TranslationResult, Translator
from tests.fixtures import create_sample_pdf_bytes


@pytest.fixture(autouse=True)
def clean_job_store():
    """Ensure the global job store is cleared before and after each test."""
    store = get_job_store()
    store.clear()
    yield
    store.clear()


# 1. Job models serialization and typing
def test_job_models_serialization_and_typing() -> None:
    """Verify Job, JobStatus, JobMode, and stats are typed and serializable."""
    stats = JobLayoutStats(
        fit_count=5,
        shrunk_count=2,
        expanded_count=1,
        review_required_count=0,
    )
    job = Job(
        filename="test.pdf",
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
        status=JobStatus.COMPLETED,
        layout_stats=stats,
        result_available=True,
    )

    assert job.status.is_terminal is True
    assert JobStatus.ANALYZING.is_terminal is False

    # Roundtrip serialization
    dumped = job.model_dump()
    assert dumped["status"] == "completed"
    assert dumped["mode"] == "demo"
    assert dumped["layout_stats"]["fit_count"] == 5

    # Safe public response
    response_model = JobResponse.model_validate(job)
    json_str = response_model.model_dump_json()
    assert "test.pdf" in json_str
    assert "fit_count" in json_str


# 2. Valid demo job creation returns 202
def test_create_demo_job_accepted_202() -> None:
    """POST /api/v1/jobs with valid PDF and demo mode returns 202 Accepted."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    response = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ("created", "analyzing", "completed")
    assert f"/api/v1/jobs/{data['job_id']}" in data["status_url"]
    assert f"/api/v1/jobs/{data['job_id']}/result" in data["result_url"]


# 3. Full demo job transition to completed
def test_demo_job_transition_to_completed() -> None:
    """Verify end-to-end execution of demo job until completed."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    create_res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("manual.pdf", pdf_bytes, "application/pdf")},
    )
    assert create_res.status_code == 202
    job_id = create_res.json()["job_id"]

    # In TestClient, tasks executed or we can poll status
    get_res = client.get(f"/api/v1/jobs/{job_id}")
    assert get_res.status_code == 200
    job_data = get_res.json()
    assert job_data["status"] == "completed"
    assert job_data["stage"] == "completed"
    assert job_data["result_available"] is True
    assert job_data["page_count"] == 2
    assert job_data["total_blocks"] > 0
    assert job_data["translated_blocks"] == job_data["total_blocks"]
    assert job_data["layout_stats"] is not None
    assert job_data["layout_stats"]["fit_count"] >= 0


# 4. Reconstructed PDF result is downloadable and valid
def test_download_job_result_pdf_validity() -> None:
    """GET /api/v1/jobs/{job_id}/result returns valid reconstructed PDF."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    create_res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("document.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = create_res.json()["job_id"]

    res_download = client.get(f"/api/v1/jobs/{job_id}/result")
    assert res_download.status_code == 200
    assert res_download.headers["content-type"] == "application/pdf"
    assert (
        "tradux-translated-document.pdf" in res_download.headers["content-disposition"]
    )
    assert res_download.content.startswith(b"%PDF-")

    # Verify opening with PyMuPDF
    doc = pymupdf.open(stream=res_download.content, filetype="pdf")
    assert len(doc) == 2
    text = doc[0].get_text()
    assert len(text) > 0
    doc.close()


# 5. Demo mode always uses MockTranslator
def test_demo_mode_always_uses_mock_translator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify demo mode strictly invokes MockTranslator deterministically."""
    from app.translators.mock import MockTranslator

    mock_init_called = False
    original_init = MockTranslator.__init__

    def spy_init(self, *args, **kwargs):
        nonlocal mock_init_called
        mock_init_called = True
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(MockTranslator, "__init__", spy_init)

    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert mock_init_called is True


# 6. Configured mode uses configured provider without exposing key
def test_configured_mode_uses_configured_provider_without_exposing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured mode uses server settings provider and never leaks API key."""
    fake_key = "sk-live-super-secret-key-tradux-987"
    custom_settings = Settings(
        translation_provider="openai",
        translation_api_key=SecretStr(fake_key),
    )

    class FakeTranslator(Translator):
        async def translate_block(
            self, text, source_language, target_language, context=None
        ):
            return TranslationResult(
                translated_text=f"[TEST_TRANSLATED] {text}",
                source_language=source_language or "en",
                target_language=target_language,
                provider="openai",
            )

    monkeypatch.setattr(
        "app.jobs.service.get_translator", lambda settings: FakeTranslator()
    )
    monkeypatch.setattr("app.jobs.service.get_settings", lambda: custom_settings)
    monkeypatch.setattr("app.api.v1.jobs.get_settings", lambda: custom_settings)

    service = TranslationJobService(store=get_job_store(), settings=custom_settings)
    monkeypatch.setattr("app.api.v1.jobs.get_job_service", lambda: service)

    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    response = client.post(
        "/api/v1/jobs",
        data={
            "target_language": "es",
            "mode": "configured",
            "confirm_configured": "true",
        },
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # Verify status response does NOT expose secret key
    get_res = client.get(f"/api/v1/jobs/{job_id}")
    assert get_res.status_code == 200
    assert fake_key not in get_res.text
    assert get_res.json()["provider"] == "openai"


# 7. Configured mode without valid config fails and does not start job
def test_configured_mode_without_valid_config_fails_and_does_not_start_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If provider is not configured, POST returns 409 and creates no job."""
    custom_settings = Settings(
        translation_provider="openai",
        translation_api_key=None,
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: custom_settings)
    monkeypatch.setattr("app.api.v1.jobs.get_settings", lambda: custom_settings)
    service = TranslationJobService(store=get_job_store(), settings=custom_settings)
    monkeypatch.setattr("app.api.v1.jobs.get_job_service", lambda: service)

    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    response = client.post(
        "/api/v1/jobs",
        data={
            "target_language": "es",
            "mode": "configured",
            "confirm_configured": "true",
        },
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 409
    assert "Configured translation provider" in response.json()["detail"]
    assert get_job_store().total_count() == 0


# 7b. Configured mode without confirmation rejected with 409
def test_configured_mode_without_confirmation_rejected_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mode=configured without confirm_configured=true returns 409."""
    factory_called = False

    def fake_factory(settings):
        nonlocal factory_called
        factory_called = True
        raise AssertionError("Factory should not have been called!")

    monkeypatch.setattr("app.jobs.service.get_translator", fake_factory)

    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    # Case 1: confirm_configured omitted completely
    res1 = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "configured"},
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )
    assert res1.status_code == 409
    assert "confirm_configured" in res1.json()["detail"]
    assert factory_called is False
    assert get_job_store().total_count() == 0

    # Case 2: confirm_configured explicitly false
    res2 = client.post(
        "/api/v1/jobs",
        data={
            "target_language": "es",
            "mode": "configured",
            "confirm_configured": "false",
        },
        files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
    )
    assert res2.status_code == 409
    assert "confirm_configured" in res2.json()["detail"]
    assert factory_called is False
    assert get_job_store().total_count() == 0


# 8. Tests perform zero real network calls
def test_offline_guarantee_raises_if_external_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure no un-mocked external network requests are permitted."""
    import httpx

    def fail_on_network(*args, **kwargs):
        raise RuntimeError("External network call prohibited in offline test!")

    monkeypatch.setattr(httpx.AsyncClient, "send", fail_on_network)
    # Running a demo job should succeed without touching network
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()
    res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("offline.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 202


# 9. Nonexistent job returns 404
def test_nonexistent_job_returns_404() -> None:
    """Querying, downloading, or deleting a missing job returns 404."""
    client = TestClient(app)
    fake_id = "00000000-0000-0000-0000-000000000000"

    assert client.get(f"/api/v1/jobs/{fake_id}").status_code == 404
    assert client.get(f"/api/v1/jobs/{fake_id}/result").status_code == 404
    assert client.delete(f"/api/v1/jobs/{fake_id}").status_code == 404


# 10. Result before completion returns 409 Conflict
def test_result_before_completion_returns_409() -> None:
    """Requesting result when job is still processing returns 409."""
    store = get_job_store()
    job = Job(
        filename="in_progress.pdf",
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
        status=JobStatus.TRANSLATING,
        stage="translating",
        result_available=False,
    )
    store.add(job, b"%PDF-source")

    client = TestClient(app)
    res = client.get(f"/api/v1/jobs/{job.job_id}/result")
    assert res.status_code == 409
    assert "still in progress" in res.json()["detail"]


# 11. Failed job remains failed with sanitized error
def test_failed_job_remains_failed_with_sanitized_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When rendering throws, job is marked FAILED and returns 400 on download."""

    def fail_render(*args, **kwargs):
        raise ValueError("Critical rendering crash")

    monkeypatch.setattr("app.jobs.service.PyMuPDFRenderer.render", fail_render)

    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()
    create_res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("crash.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = create_res.json()["job_id"]

    get_res = client.get(f"/api/v1/jobs/{job_id}")
    assert get_res.status_code == 200
    job_data = get_res.json()
    assert job_data["status"] == "failed"
    assert job_data["error_code"] == "ValueError"
    assert job_data["error_message"] == "Error en el procesamiento del documento"

    # Downloading failed result returns 400
    res_download = client.get(f"/api/v1/jobs/{job_id}/result")
    assert res_download.status_code == 400


# 12. Confidential marker in exception not leaked in HTTP or logs
def test_confidential_marker_not_leaked_in_http_or_logs(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ensure sensitive text in an exception is never exposed in response or logs."""
    secret_marker = "TRADUX_SECRET_KEY_XYZ_98765"

    def fail_with_secret(*args, **kwargs):
        raise RuntimeError(f"Failure with sensitive marker: {secret_marker}")

    monkeypatch.setattr("app.jobs.service.LayoutEngine.build", fail_with_secret)

    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    with caplog.at_level(logging.ERROR):
        create_res = client.post(
            "/api/v1/jobs",
            data={"target_language": "es", "mode": "demo"},
            files={"file": ("leak_test.pdf", pdf_bytes, "application/pdf")},
        )
        job_id = create_res.json()["job_id"]
        get_res = client.get(f"/api/v1/jobs/{job_id}")

    assert secret_marker not in get_res.text
    assert secret_marker not in caplog.text


# 13. Upload validation errors
def test_upload_validation_errors() -> None:
    """Test rejection for missing/empty/corrupted PDF and bad mode/language."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    # Empty PDF
    res_empty = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert res_empty.status_code == 400

    # Corrupted PDF
    res_corrupt = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("bad.pdf", b"not-a-pdf-file", "application/pdf")},
    )
    assert res_corrupt.status_code == 400

    # Missing target language
    res_no_target = client.post(
        "/api/v1/jobs",
        data={"target_language": "   ", "mode": "demo"},
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_no_target.status_code == 422

    # Unsupported target language
    res_bad_target = client.post(
        "/api/v1/jobs",
        data={"target_language": "banana", "mode": "demo"},
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_bad_target.status_code == 422
    assert "Unsupported target language" in res_bad_target.json()["detail"]

    # Unsupported source language
    res_bad_source = client.post(
        "/api/v1/jobs",
        data={
            "target_language": "es",
            "source_language": "banana",
            "mode": "demo",
        },
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_bad_source.status_code == 422
    assert "Unsupported source language" in res_bad_source.json()["detail"]

    # Invalid mode
    res_bad_mode = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "hyper-speed"},
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_bad_mode.status_code == 422


# 13b. Language normalization and auto detection
def test_language_normalization_and_validation() -> None:
    """Uppercase language codes like ES and EN normalize cleanly to es and en."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    res = client.post(
        "/api/v1/jobs",
        data={
            "target_language": "  ES  ",
            "source_language": "  EN  ",
            "mode": "demo",
        },
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]
    job_data = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job_data["target_language"] == "es"
    assert job_data["source_language"] == "en"

    # source_language="auto" normalizes to None
    res_auto = client.post(
        "/api/v1/jobs",
        data={
            "target_language": "nl",
            "source_language": "auto",
            "mode": "demo",
        },
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert res_auto.status_code == 202
    auto_job_id = res_auto.json()["job_id"]
    auto_job = client.get(f"/api/v1/jobs/{auto_job_id}").json()
    assert auto_job["source_language"] is None


# 14. Download filename sanitized
def test_download_filename_sanitized() -> None:
    """Filename with traversal or special characters is sanitized on download."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    create_res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={
            "file": ("../../malicious # doc @ name.pdf", pdf_bytes, "application/pdf")
        },
    )
    job_id = create_res.json()["job_id"]

    res_download = client.get(f"/api/v1/jobs/{job_id}/result")
    assert res_download.status_code == 200
    cd_header = res_download.headers["content-disposition"]
    assert ".." not in cd_header
    assert "#" not in cd_header
    assert "@" not in cd_header


# 15. Cleanup and TTL removes expired jobs
def test_job_store_ttl_cleanup_removes_expired_jobs() -> None:
    """Jobs exceeding TTL are evicted upon access or cleanup."""
    store = JobStore(ttl_seconds=10)
    job = Job(
        filename="old.pdf",
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
        status=JobStatus.COMPLETED,
    )
    store.add(job, b"%PDF")

    # Manually age job beyond TTL
    job_ref = store._jobs[job.job_id]
    job_ref.created_at = datetime.now(UTC) - timedelta(seconds=20)

    # get() evicts expired job
    assert store.get(job.job_id) is None
    assert store.total_count() == 0


# 16. Store capacity pruning prevents unbounded growth
def test_job_store_capacity_pruning_prevents_unbounded_growth() -> None:
    """Store with max_retained_jobs prunes oldest completed jobs."""
    store = JobStore(ttl_seconds=3600, max_retained_jobs=3)

    for i in range(5):
        j = Job(
            filename=f"doc_{i}.pdf",
            target_language="es",
            mode=JobMode.DEMO,
            provider="mock",
            status=JobStatus.COMPLETED,
        )
        store.add(j, b"%PDF")

    assert store.total_count() <= 3


# 17. Pipeline orchestrates components without internal HTTP calls
def test_pipeline_orchestration_without_internal_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify pipeline executes analyzer -> engine -> layout -> renderer in-memory."""
    store = get_job_store()
    service = TranslationJobService(store=store)
    pdf_bytes = create_sample_pdf_bytes()

    job = service.create_job(
        filename="in_process.pdf",
        source_pdf=pdf_bytes,
        target_language="es",
        mode=JobMode.DEMO,
    )

    asyncio.run(service.run_job(job.job_id))
    completed_job = store.get(job.job_id)
    assert completed_job.status == JobStatus.COMPLETED
    assert store.get_result(job.job_id) is not None


# 18. Output PDF opens with PyMuPDF
def test_output_pdf_opens_with_pymupdf() -> None:
    """Rendered PDF opens cleanly and has pages."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("open_test.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = res.json()["job_id"]
    pdf_out = client.get(f"/api/v1/jobs/{job_id}/result").content

    doc = pymupdf.open(stream=pdf_out, filetype="pdf")
    assert doc.page_count == 2
    doc.close()


# 19. Original source PDF remains immutable
def test_source_pdf_remains_immutable() -> None:
    """Source PDF bytes are not modified during the pipeline."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()
    original_copy = bytes(pdf_bytes)

    client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("immutable.pdf", pdf_bytes, "application/pdf")},
    )
    assert pdf_bytes == original_copy


# 20. Final layout metrics reach job status
def test_final_layout_metrics_reach_job_status() -> None:
    """Job status contains fit, shrunk, expanded, and review counts."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("metrics.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = res.json()["job_id"]
    job_info = client.get(f"/api/v1/jobs/{job_id}").json()

    assert "layout_stats" in job_info
    stats = job_info["layout_stats"]
    assert isinstance(stats["fit_count"], int)
    assert isinstance(stats["shrunk_count"], int)
    assert isinstance(stats["expanded_count"], int)
    assert isinstance(stats["review_required_count"], int)


# 21. review_required reflected in job state and headers
def test_review_required_reflected_in_job_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a block cannot fit, review_required is reflected in state and headers."""
    from app.layout.engine import LayoutEngine
    from app.layout.models import LayoutStats, LayoutStatus

    original_build = LayoutEngine.build

    def build_with_review(self, doc):
        layout = original_build(self, doc)
        if layout.pages and layout.pages[0].blocks:
            b0 = layout.pages[0].blocks[0]
            new_b0 = b0.model_copy(update={"status": LayoutStatus.REVIEW_REQUIRED})
            new_blocks = list(layout.pages[0].blocks)
            new_blocks[0] = new_b0
            new_p0 = layout.pages[0].model_copy(update={"blocks": new_blocks})
            new_pages = list(layout.pages)
            new_pages[0] = new_p0
            new_stats = LayoutStats(
                total_blocks=layout.stats.total_blocks,
                fit_count=layout.stats.fit_count,
                shrunk_count=max(0, layout.stats.shrunk_count - 1),
                expanded_count=layout.stats.expanded_count,
                review_required_count=layout.stats.review_required_count + 1,
            )
            layout = layout.model_copy(update={"pages": new_pages, "stats": new_stats})
        return layout

    monkeypatch.setattr(LayoutEngine, "build", build_with_review)

    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("overflow.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = res.json()["job_id"]

    job_info = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job_info["layout_stats"]["review_required_count"] >= 1

    result_res = client.get(f"/api/v1/jobs/{job_id}/result")
    assert result_res.status_code == 200
    assert int(result_res.headers["X-Tradux-Review-Blocks"]) >= 1


# 22. Capabilities endpoint never contains secrets
def test_capabilities_endpoint_never_contains_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/v1/capabilities returns only public configuration."""
    fake_key = "sk-super-confidential-openai-token"
    settings = Settings(
        translation_provider="openai",
        translation_api_key=SecretStr(fake_key),
        translation_api_base_url="https://private-endpoint.internal",
    )
    monkeypatch.setattr("app.api.v1.capabilities.get_settings", lambda: settings)

    client = TestClient(app)
    res = client.get("/api/v1/capabilities")
    assert res.status_code == 200
    assert fake_key not in res.text
    assert "private-endpoint.internal" not in res.text

    data = res.json()
    assert data["demo_translation"] is True
    assert data["configured_translation_available"] is True
    assert data["configured_provider"] == "openai"
    assert data["max_upload_size_mb"] > 0


# 23. UI contains mode selector, notice, and confirmation modal
def test_ui_contains_demo_and_real_controls_and_modal() -> None:
    """GET / renders HTML containing mode options, notice, and modal."""
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "radio-mode-demo" in html
    assert "radio-mode-configured" in html
    assert "demo-notice-banner" in html
    assert "cost-notice-banner" in html
    assert "confirm-modal" in html
    assert "btn-start-job" in html


# 24. Delete job frees memory buffers
def test_delete_job_frees_memory_buffers() -> None:
    """DELETE /api/v1/jobs/{job_id} cleans up job and buffered PDF."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    create_res = client.post(
        "/api/v1/jobs",
        data={"target_language": "es", "mode": "demo"},
        files={"file": ("to_delete.pdf", pdf_bytes, "application/pdf")},
    )
    job_id = create_res.json()["job_id"]

    del_res = client.delete(f"/api/v1/jobs/{job_id}")
    assert del_res.status_code == 204

    # Subsequent GET returns 404
    assert client.get(f"/api/v1/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}/result").status_code == 404


# 25. Complete local web flow
def test_complete_local_web_flow() -> None:
    """End-to-end simulation of user workflow via API."""
    client = TestClient(app)
    pdf_bytes = create_sample_pdf_bytes()

    # Step 1: Capabilities
    caps = client.get("/api/v1/capabilities").json()
    assert caps["demo_translation"] is True

    # Step 2: Analyze PDF
    analyze_res = client.post(
        "/api/v1/documents/analyze",
        files={"file": ("flow.pdf", pdf_bytes, "application/pdf")},
    )
    assert analyze_res.status_code == 200
    doc = analyze_res.json()
    assert doc["page_count"] == 2

    # Step 3: Create translation job
    job_res = client.post(
        "/api/v1/jobs",
        data={
            "target_language": "es",
            "source_language": "en",
            "mode": "demo",
            "protected_terms": "Tradux, MODEL-X100",
        },
        files={"file": ("flow.pdf", pdf_bytes, "application/pdf")},
    )
    assert job_res.status_code == 202
    job_id = job_res.json()["job_id"]

    # Step 4: Poll status until completed
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "completed"

    # Step 5: Download PDF
    download_res = client.get(f"/api/v1/jobs/{job_id}/result")
    assert download_res.status_code == 200
    assert download_res.content.startswith(b"%PDF-")


# 26. DELETE active job is rejected with 409
def test_delete_active_job_rejected_with_409() -> None:
    """Cannot delete an active translation job while it is running."""
    store = get_job_store()
    job = Job(
        filename="active.pdf",
        file_size=100,
        page_count=1,
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
        status=JobStatus.LAYOUT,
        stage="layout",
    )
    store.add(job, b"%PDF-1.4 mock")

    client = TestClient(app)
    res = client.delete(f"/api/v1/jobs/{job.job_id}")
    assert res.status_code == 409
    assert "Cannot delete an active translation job" in res.json()["detail"]

    # Job still present in store
    assert store.get(job.job_id) is not None


# 27. Active jobs are never purged by TTL or capacity
def test_active_jobs_not_purged_by_ttl_or_capacity() -> None:
    """Active jobs remain in store even when exceeding TTL or capacity limits."""
    from datetime import UTC, datetime, timedelta

    store = JobStore(max_retained_jobs=2, ttl_seconds=10)
    old_time = datetime.now(UTC) - timedelta(seconds=50)

    active_job = Job(
        filename="running.pdf",
        file_size=100,
        page_count=1,
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
        status=JobStatus.TRANSLATING,
        stage="translating",
        created_at=old_time,
    )
    store.add(active_job, b"pdf_data")

    # TTL cleanup should NOT remove active job
    removed = store.cleanup_expired()
    assert removed == 0
    assert store.get(active_job.job_id) is not None

    # Capacity enforcement should NOT remove active job
    terminal_job = Job(
        filename="done.pdf",
        file_size=100,
        page_count=1,
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
        status=JobStatus.COMPLETED,
        stage="completed",
        created_at=old_time,
    )
    store.add(terminal_job, b"pdf_done")

    another_job = Job(
        filename="done2.pdf",
        file_size=100,
        page_count=1,
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
        status=JobStatus.COMPLETED,
        stage="completed",
    )
    store.add(another_job, b"pdf_done2")

    # The active job MUST still be retained
    assert store.get(active_job.job_id) is not None


# 28. Event loop is not blocked during background job execution
@pytest.mark.asyncio
async def test_event_loop_not_blocked_during_job_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FastAPI event loop remains responsive (e.g. GET /health) while job runs."""
    import asyncio
    import time

    import httpx

    from app.jobs.models import Job, JobMode, JobStatus
    from app.jobs.service import get_job_service
    from app.layout.engine import LayoutEngine
    from app.main import app as fastapi_app

    service = get_job_service()
    pdf_bytes = create_sample_pdf_bytes()
    job = Job(
        filename="async_concurrency_test.pdf",
        file_size=len(pdf_bytes),
        page_count=2,
        target_language="es",
        mode=JobMode.DEMO,
        provider="mock",
    )
    service.store.add(job, pdf_bytes)

    original_build = LayoutEngine.build

    def slow_build(self, doc):
        time.sleep(0.2)
        return original_build(self, doc)

    monkeypatch.setattr(LayoutEngine, "build", slow_build)

    job_task = asyncio.create_task(service.run_job(job.job_id))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test"
    ) as client:
        # Give run_job a brief tick to start running
        await asyncio.sleep(0.02)

        # Health endpoint responds while background stage is sleeping in thread
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # Active job status endpoint also responds concurrently
        status_res = await client.get(f"/api/v1/jobs/{job.job_id}")
        assert status_res.status_code == 200
        assert status_res.json()["status"] in (
            JobStatus.ANALYZING.value,
            JobStatus.TRANSLATING.value,
            JobStatus.LAYOUT.value,
            JobStatus.RENDERING.value,
            JobStatus.COMPLETED.value,
        )

    await job_task
    final_job = service.store.get(job.job_id)
    assert final_job is not None
    assert final_job.status == JobStatus.COMPLETED
