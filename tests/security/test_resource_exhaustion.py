from __future__ import annotations

import pytest

from agent.core.contract.schema import ExecutionContract
from agent.sandbox.runner import SandboxRunner

pytestmark = pytest.mark.security


@pytest.fixture(scope="module")
def runner() -> SandboxRunner:
    return SandboxRunner()


def _contract(max_seconds: int) -> ExecutionContract:
    return ExecutionContract(intent_summary="resource exhaustion test", max_execution_seconds=max_seconds)


def test_infinite_loop_is_terminated_by_timeout(runner: SandboxRunner) -> None:
    code = "while True:\n    pass"
    result = runner.run(code, _contract(max_seconds=5), session_id="test-infinite-loop", attempt_number=1)

    assert result.timed_out is True
    assert result.duration_seconds < 15


def test_fork_bomb_is_contained_by_pids_limit(runner: SandboxRunner) -> None:
    code = (
        "import os\n"
        "import time\n"
        "try:\n"
        "    for _ in range(1000):\n"
        "        pid = os.fork()\n"
        "        if pid == 0:\n"
        "            time.sleep(10)\n"
        "            os._exit(0)\n"
        "except OSError as e:\n"
        "    print('FORK_BLOCKED:', e)"
    )
    result = runner.run(code, _contract(max_seconds=10), session_id="test-fork-bomb", attempt_number=1)

    assert result.timed_out is True or "FORK_BLOCKED" in result.stdout or result.exit_code != 0


def test_memory_bomb_is_killed_before_host_impact(runner: SandboxRunner) -> None:
    code = (
        "chunks = []\n"
        "try:\n"
        "    while True:\n"
        "        chunks.append(bytearray(10**8))\n"
        "except MemoryError:\n"
        "    print('MEMORY_ERROR_RAISED')"
    )
    result = runner.run(code, _contract(max_seconds=15), session_id="test-memory-bomb", attempt_number=1)

    assert result.timed_out is True or result.exit_code != 0


def test_cpu_intensive_task_respects_wall_clock_timeout(runner: SandboxRunner) -> None:
    code = (
        "total = 0\n"
        "for i in range(10**12):\n"
        "    total += i * i\n"
        "print(total)"
    )
    result = runner.run(code, _contract(max_seconds=5), session_id="test-cpu-bound", attempt_number=1)

    assert result.timed_out is True
    assert result.duration_seconds < 15


def test_excessive_file_descriptors_are_limited(runner: SandboxRunner) -> None:
    code = (
        "handles = []\n"
        "try:\n"
        "    for i in range(100000):\n"
        "        handles.append(open(f'/tmp/fd_test_{i}', 'w'))\n"
        "    print('OPENED_ALL:', len(handles))\n"
        "except OSError as e:\n"
        "    print('FD_LIMIT_HIT:', len(handles))"
    )
    result = runner.run(code, _contract(max_seconds=15), session_id="test-fd-exhaustion", attempt_number=1)

    assert "OPENED_ALL: 100000" not in result.stdout
    assert "FD_LIMIT_HIT" in result.stdout
