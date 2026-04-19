"""TDD tests for worker helpers (pure pieces extracted from echoes_pipeline).

These helpers keep the worker's orchestration code small and readable by
pulling out decisions that don't touch the network or the filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from echoes.worker import (
    build_failure_update,
    build_splat_storage_prefix,
    content_type_for_upload,
    delete_local_video,
    job_log_prefix,
    should_download_video,
)


class TestContentTypeForUpload:
    def test_json_file_is_application_json(self):
        assert content_type_for_upload(Path("manifest.json")) == "application/json"

    def test_splat_file_is_octet_stream(self):
        assert (
            content_type_for_upload(Path("frame_000.splat"))
            == "application/octet-stream"
        )

    def test_is_case_insensitive_for_json_suffix(self):
        assert content_type_for_upload(Path("weird.JSON")) == "application/json"


class TestBuildSplatStoragePrefix:
    def test_joins_user_and_memory_with_slash(self):
        assert build_splat_storage_prefix("alice", "mem42") == "alice/mem42"

    def test_rejects_empty_user_id(self):
        with pytest.raises(ValueError):
            build_splat_storage_prefix("", "mem42")

    def test_rejects_empty_memory_id(self):
        with pytest.raises(ValueError):
            build_splat_storage_prefix("alice", "")


class TestShouldDownloadVideo:
    def test_true_when_file_missing(self, tmp_path: Path):
        assert should_download_video(tmp_path / "missing.mp4") is True

    def test_false_when_file_exists(self, tmp_path: Path):
        p = tmp_path / "input.mp4"
        p.write_bytes(b"data")
        assert should_download_video(p) is False

    def test_true_when_file_exists_but_empty(self, tmp_path: Path):
        p = tmp_path / "input.mp4"
        p.touch()
        assert should_download_video(p) is True


class TestBuildFailureUpdate:
    def test_includes_processing_failed_status(self):
        payload = build_failure_update(RuntimeError("boom"))
        assert payload["status"] == "processing_failed"

    def test_stores_error_text_on_safety_flag_field(self):
        payload = build_failure_update(RuntimeError("disk full"))
        assert "disk full" in payload["safety_flag"]

    def test_truncates_very_long_error_messages(self):
        payload = build_failure_update(RuntimeError("x" * 5000))
        # Keep the DB happy: safety_flag is a free-text column but storing
        # a 5 KB stacktrace tail is noise. Cap at a reasonable length.
        assert len(payload["safety_flag"]) <= 500


class TestDeleteLocalVideo:
    def test_removes_existing_file(self, tmp_path: Path):
        video = tmp_path / "input.mp4"
        video.write_bytes(b"frames")
        delete_local_video(video)
        assert not video.exists()

    def test_returns_true_when_file_existed(self, tmp_path: Path):
        video = tmp_path / "input.mp4"
        video.write_bytes(b"x")
        assert delete_local_video(video) is True

    def test_returns_false_when_file_already_missing(self, tmp_path: Path):
        assert delete_local_video(tmp_path / "gone.mp4") is False

    def test_does_not_crash_when_file_missing(self, tmp_path: Path):
        # Explicit: the retention policy runs cleanup unconditionally, so
        # "file already deleted" must be a normal case, not an exception.
        delete_local_video(tmp_path / "gone.mp4")

    def test_does_not_crash_when_parent_dir_missing(self, tmp_path: Path):
        delete_local_video(tmp_path / "ghost" / "input.mp4")


class TestJobLogPrefix:
    def test_includes_memory_id(self):
        assert "abc123" in job_log_prefix("abc123", "download")

    def test_includes_stage(self):
        assert "download" in job_log_prefix("abc123", "download")

    def test_is_stable_format_across_stages(self):
        a = job_log_prefix("mem", "download")
        b = job_log_prefix("mem", "upload")
        # Same prefix shape, different stage token: the non-stage part lines up
        assert a.replace("download", "X") == b.replace("upload", "X")
