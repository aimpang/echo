"""TDD tests for the 4DGaussians preflight / setup helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from echoes.fourdgs.preflight import (
    REQUIRED_BINARIES,
    REQUIRED_ENV_VARS,
    build_4dgaussians_clone_cmd,
    check_preflight,
    format_preflight_report,
)


class TestRequiredConstants:
    def test_binaries_include_ffmpeg_and_colmap(self):
        assert "ffmpeg" in REQUIRED_BINARIES
        assert "colmap" in REQUIRED_BINARIES

    def test_env_vars_include_fourdgs_paths(self):
        assert "FOURDGS_REPO_DIR" in REQUIRED_ENV_VARS
        assert "FOURDGS_CONFIG" in REQUIRED_ENV_VARS


class TestCheckPreflight:
    def test_all_present_returns_empty_issues(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        cfg = repo / "config.py"
        cfg.touch()
        issues = check_preflight(
            env={"FOURDGS_REPO_DIR": str(repo), "FOURDGS_CONFIG": str(cfg)},
            which=lambda _: "/usr/bin/fake",
        )
        assert issues == []

    def test_reports_missing_binaries(self, tmp_path: Path):
        issues = check_preflight(
            env={"FOURDGS_REPO_DIR": str(tmp_path), "FOURDGS_CONFIG": str(tmp_path)},
            which=lambda _: None,
        )
        messages = " ".join(issues)
        for name in REQUIRED_BINARIES:
            assert name in messages

    def test_reports_missing_env_vars(self, tmp_path: Path):
        issues = check_preflight(env={}, which=lambda _: "/usr/bin/fake")
        messages = " ".join(issues)
        for name in REQUIRED_ENV_VARS:
            assert name in messages

    def test_reports_nonexistent_repo_dir(self):
        issues = check_preflight(
            env={
                "FOURDGS_REPO_DIR": "/definitely/does/not/exist",
                "FOURDGS_CONFIG": "/definitely/does/not/exist/config.py",
            },
            which=lambda _: "/usr/bin/fake",
        )
        assert any("FOURDGS_REPO_DIR" in i and "exist" in i.lower() for i in issues)

    def test_reports_nonexistent_config_file(self, tmp_path: Path):
        issues = check_preflight(
            env={
                "FOURDGS_REPO_DIR": str(tmp_path),
                "FOURDGS_CONFIG": str(tmp_path / "missing.py"),
            },
            which=lambda _: "/usr/bin/fake",
        )
        assert any("FOURDGS_CONFIG" in i and "exist" in i.lower() for i in issues)


class TestFormatPreflightReport:
    def test_empty_issues_says_ready(self):
        assert "ready" in format_preflight_report([]).lower()

    def test_includes_each_issue(self):
        report = format_preflight_report(["missing ffmpeg", "missing colmap"])
        assert "ffmpeg" in report
        assert "colmap" in report


class TestCloneCmd:
    def test_clones_hustvl_repo(self, tmp_path: Path):
        cmd = build_4dgaussians_clone_cmd(tmp_path / "4DGaussians")
        assert "git" in cmd
        assert "clone" in cmd
        assert any("hustvl/4DGaussians" in part for part in cmd)

    def test_recurse_submodules(self, tmp_path: Path):
        cmd = build_4dgaussians_clone_cmd(tmp_path / "repo")
        assert "--recurse-submodules" in cmd
