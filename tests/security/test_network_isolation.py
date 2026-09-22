from __future__ import annotations

import pytest

from agent.core.contract.schema import ExecutionContract
from agent.sandbox.runner import SandboxRunner

pytestmark = pytest.mark.security


@pytest.fixture(scope="module")
def runner() -> SandboxRunner:
    return SandboxRunner()


def _contract(requires_network: bool, max_seconds: int = 10) -> ExecutionContract:
    return ExecutionContract(
        intent_summary="network isolation test",
        requires_network=requires_network,
        max_execution_seconds=max_seconds,
    )


def test_network_none_blocks_dns_resolution(runner: SandboxRunner) -> None:
    code = (
        "import socket\n"
        "try:\n"
        "    socket.gethostbyname('example.com')\n"
        "    print('DNS_SUCCEEDED')\n"
        "except Exception as e:\n"
        "    print('DNS_BLOCKED:', type(e).__name__)"
    )
    result = runner.run(code, _contract(requires_network=False), session_id="test-dns-block", attempt_number=1)

    assert "DNS_SUCCEEDED" not in result.stdout


def test_network_none_blocks_cloud_metadata_endpoint(runner: SandboxRunner) -> None:
    code = (
        "import urllib.request\n"
        "try:\n"
        "    req = urllib.request.Request('http://169.254.169.254/latest/meta-data/')\n"
        "    urllib.request.urlopen(req, timeout=5)\n"
        "    print('METADATA_REACHED')\n"
        "except Exception as e:\n"
        "    print('METADATA_BLOCKED:', type(e).__name__)"
    )
    result = runner.run(code, _contract(requires_network=False), session_id="test-metadata-block", attempt_number=1)

    assert "METADATA_REACHED" not in result.stdout


def test_network_none_blocks_localhost_access(runner: SandboxRunner) -> None:
    code = (
        "import socket\n"
        "try:\n"
        "    s = socket.create_connection(('127.0.0.1', 22), timeout=3)\n"
        "    print('LOCALHOST_REACHED')\n"
        "except Exception as e:\n"
        "    print('LOCALHOST_BLOCKED:', type(e).__name__)"
    )
    result = runner.run(code, _contract(requires_network=False), session_id="test-localhost-block", attempt_number=1)

    assert "LOCALHOST_REACHED" not in result.stdout


def test_network_bridge_mode_allows_outbound_when_explicitly_enabled(runner: SandboxRunner) -> None:
    code = (
        "import urllib.request\n"
        "try:\n"
        "    urllib.request.urlopen('http://example.com', timeout=8)\n"
        "    print('NETWORK_REACHED')\n"
        "except Exception as e:\n"
        "    print('NETWORK_FAILED:', type(e).__name__)"
    )
    result = runner.run(code, _contract(requires_network=True), session_id="test-network-enabled", attempt_number=1)

    assert result.exit_code is not None
