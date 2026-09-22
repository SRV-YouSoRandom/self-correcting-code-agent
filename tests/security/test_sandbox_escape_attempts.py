from __future__ import annotations

import pytest

from agent.core.contract.schema import ExecutionContract
from agent.sandbox.runner import SandboxRunner

pytestmark = pytest.mark.security


@pytest.fixture(scope="module")
def runner() -> SandboxRunner:
    return SandboxRunner()


def _contract(max_seconds: int = 10) -> ExecutionContract:
    return ExecutionContract(intent_summary="security test", max_execution_seconds=max_seconds)


def test_reads_containers_own_passwd_not_host_passwd(runner: SandboxRunner) -> None:
    code = (
        "with open('/etc/passwd') as f:\n"
        "    content = f.read()\n"
        "print('CONTENT_LEN:', len(content))\n"
        "print('HAS_SANDBOX_USER:', 'sandbox' in content)"
    )
    result = runner.run(code, _contract(), session_id="test-etc-passwd", attempt_number=1)

    assert "HAS_SANDBOX_USER: True" in result.stdout
    content_len_line = next(line for line in result.stdout.splitlines() if line.startswith("CONTENT_LEN"))
    content_len = int(content_len_line.split(":")[1].strip())
    assert content_len < 2000


def test_cannot_access_docker_socket(runner: SandboxRunner) -> None:
    code = (
        "import os\n"
        "print('socket exists:', os.path.exists('/var/run/docker.sock'))"
    )
    result = runner.run(code, _contract(), session_id="test-docker-socket", attempt_number=1)

    assert "socket exists: False" in result.stdout


def test_cannot_write_outside_workspace(runner: SandboxRunner) -> None:
    code = (
        "try:\n"
        "    with open('/etc/malicious_test_file', 'w') as f:\n"
        "        f.write('escaped')\n"
        "    print('WRITE_SUCCEEDED')\n"
        "except Exception as e:\n"
        "    print('WRITE_BLOCKED:', type(e).__name__)"
    )
    result = runner.run(code, _contract(), session_id="test-write-outside", attempt_number=1)

    assert "WRITE_SUCCEEDED" not in result.stdout


def test_cannot_escalate_to_root(runner: SandboxRunner) -> None:
    code = (
        "import os\n"
        "print('uid:', os.getuid())\n"
        "print('is_root:', os.getuid() == 0)"
    )
    result = runner.run(code, _contract(), session_id="test-root-escalation", attempt_number=1)

    assert "is_root: False" in result.stdout


def test_process_capabilities_are_dropped(runner: SandboxRunner) -> None:
    code = (
        "try:\n"
        "    import subprocess\n"
        "    result = subprocess.run(['cat', '/proc/1/status'], capture_output=True, text=True, timeout=5)\n"
        "    print('CapEff' in result.stdout)\n"
        "    for line in result.stdout.splitlines():\n"
        "        if line.startswith('CapEff'):\n"
        "            print(line)\n"
        "except Exception as e:\n"
        "    print('FAILED:', e)"
    )
    result = runner.run(code, _contract(), session_id="test-capabilities", attempt_number=1)

    assert result.exit_code is not None


def test_cannot_read_agent_env_file(runner: SandboxRunner) -> None:
    code = (
        "import os\n"
        "print('OPENROUTER_API_KEY' in os.environ)\n"
        "print('GEMINI_API_KEY' in os.environ)"
    )
    result = runner.run(code, _contract(), session_id="test-env-leak", attempt_number=1)

    assert "OPENROUTER_API_KEY' in os.environ) True" not in result.stdout
    lines = [line for line in result.stdout.splitlines() if line.strip() in ("True", "False")]
    assert all(line.strip() == "False" for line in lines)
