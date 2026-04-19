"""TDD for the ``run_logged`` subprocess wrapper.

We wrap every external command (ffmpeg, colmap, 4DGaussians train/render)
so that:

* a hang is bounded by an explicit timeout
* stderr is captured and written to the log on failure, not lost to the void
* the raised exception still has the original ``returncode``/``cmd`` so
  callers can keep using ``except subprocess.CalledProcessError``.
"""

from __future__ import annotations

import logging
import subprocess
import sys

import pytest

from echoes._subprocess import run_logged


def _python_cmd(script: str) -> list[str]:
    return [sys.executable, "-c", script]


class TestRunLogged:
    def test_returns_completed_process_on_success(self):
        cp = run_logged(_python_cmd("print('hi')"), timeout=10)
        assert cp.returncode == 0

    def test_raises_called_process_error_on_nonzero_exit(self):
        with pytest.raises(subprocess.CalledProcessError):
            run_logged(_python_cmd("import sys; sys.exit(3)"), timeout=10)

    def test_logs_stderr_tail_on_failure(self, caplog):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(subprocess.CalledProcessError):
                run_logged(
                    _python_cmd(
                        "import sys; sys.stderr.write('BOOM\\n'); sys.exit(2)"
                    ),
                    timeout=10,
                )
        assert any("BOOM" in rec.message for rec in caplog.records)

    def test_raises_timeout_expired_when_command_hangs(self):
        with pytest.raises(subprocess.TimeoutExpired):
            run_logged(
                _python_cmd("import time; time.sleep(5)"),
                timeout=0.5,
            )

    def test_passes_cwd_through(self, tmp_path):
        cp = run_logged(
            _python_cmd("import os; print(os.getcwd())"),
            timeout=10,
            cwd=tmp_path,
        )
        assert str(tmp_path) in cp.stdout

    def test_captures_stdout_and_stderr_into_completed_process(self):
        cp = run_logged(
            _python_cmd(
                "import sys; print('out'); sys.stderr.write('err\\n')"
            ),
            timeout=10,
        )
        assert "out" in cp.stdout
        assert "err" in cp.stderr
