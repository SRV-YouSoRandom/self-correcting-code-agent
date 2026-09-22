from __future__ import annotations

import pytest

from agent.core.contract.schema import ExecutionContract
from agent.sandbox.runner import SandboxRunner

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def runner() -> SandboxRunner:
    return SandboxRunner()


def _contract(max_seconds: int = 10, requires_network: bool = False) -> ExecutionContract:
    return ExecutionContract(
        intent_summary="test task",
        requires_network=requires_network,
        max_execution_seconds=max_seconds,
    )


def test_successful_execution_returns_correct_output(runner: SandboxRunner) -> None:
    code = "print('integration test output')"
    result = runner.run(code, _contract(), session_id="test-success", attempt_number=1)

    assert result.exit_code == 0
    assert "integration test output" in result.stdout
    assert result.timed_out is False


def test_failing_code_captures_stderr_and_exit_code(runner: SandboxRunner) -> None:
    code = "raise ValueError('deliberate failure')"
    result = runner.run(code, _contract(), session_id="test-failure", attempt_number=1)

    assert result.exit_code == 1
    assert "ValueError" in result.stderr
    assert "deliberate failure" in result.stderr


def test_timeout_is_enforced(runner: SandboxRunner) -> None:
    code = "import time\ntime.sleep(30)"
    result = runner.run(code, _contract(max_seconds=3), session_id="test-timeout", attempt_number=1)

    assert result.timed_out is True
    assert result.duration_seconds < 10


def test_network_disabled_by_default_blocks_external_requests(runner: SandboxRunner) -> None:
    code = (
        "import urllib.request\n"
        "urllib.request.urlopen('http://example.com', timeout=5)\n"
        "print('should not reach here')"
    )
    result = runner.run(code, _contract(requires_network=False), session_id="test-network-block", attempt_number=1)

    assert result.exit_code != 0
    assert "should not reach here" not in result.stdout


def test_memory_limit_kills_process_that_exceeds_it(runner: SandboxRunner) -> None:
    code = (
        "data = []\n"
        "while True:\n"
        "    data.append(' ' * 10**7)\n"
    )
    result = runner.run(code, _contract(max_seconds=15), session_id="test-memory-limit", attempt_number=1)

    assert result.exit_code != 0 or result.timed_out is True


def test_workspace_is_isolated_between_runs(runner: SandboxRunner) -> None:
    write_code = "with open('leftover.txt', 'w') as f:\n    f.write('should not persist')"
    runner.run(write_code, _contract(), session_id="test-isolation", attempt_number=1)

    read_code = (
        "import os\n"
        "print('leftover.txt exists:', os.path.exists('leftover.txt'))"
    )
    result = runner.run(read_code, _contract(), session_id="test-isolation", attempt_number=2)

    assert "leftover.txt exists: False" in result.stdout


def test_available_libraries_are_importable(runner: SandboxRunner) -> None:
    code = (
        "import requests\n"
        "import bs4\n"
        "import pandas\n"
        "import matplotlib\n"
        "import numpy\n"
        "print('all imports succeeded')"
    )
    result = runner.run(code, _contract(), session_id="test-libraries", attempt_number=1)

    assert result.exit_code == 0
    assert "all imports succeeded" in result.stdout


def test_artifact_is_persisted_and_readable(runner: SandboxRunner) -> None:
    code = "with open('output.txt', 'w') as f:\n    f.write('artifact content')"
    result = runner.run(code, _contract(), session_id="test-artifact", attempt_number=1)

    assert len(result.artifact_paths) == 1
    from pathlib import Path

    artifact_path = Path(result.artifact_paths[0])
    assert artifact_path.exists()
    assert artifact_path.read_text() == "artifact content"
