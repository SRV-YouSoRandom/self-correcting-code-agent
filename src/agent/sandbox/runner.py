from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

import docker
from docker.errors import ImageNotFound, NotFound

from agent.core.contract.schema import ExecutionContract
from agent.core.state import ExecutionResult
from agent.sandbox.artifact_extractor import persist_all_output_files, persist_expected_artifacts
from agent.sandbox.limits import ResourceLimits, limits_from_contract_seconds
from agent.sandbox.network_policy import NetworkPolicy, policy_from_contract

SANDBOX_IMAGE_NAME = os.environ.get("SANDBOX_IMAGE_NAME", "agent-sandbox:latest")
SANDBOX_RUNTIME = os.environ.get("SANDBOX_RUNTIME")
SCRIPT_FILENAME = "script.py"
POLL_INTERVAL_SECONDS = 0.25


class SandboxRunner:
    def __init__(self) -> None:
        self._client = docker.from_env()
        self._ensure_image_exists()

    def _ensure_image_exists(self) -> None:
        try:
            self._client.images.get(SANDBOX_IMAGE_NAME)
        except ImageNotFound as exc:
            raise RuntimeError(
                f"Sandbox image '{SANDBOX_IMAGE_NAME}' not found. "
                f"Run ./scripts/build_sandbox_image.sh first."
            ) from exc

    def run(
        self,
        code: str,
        contract: ExecutionContract,
        session_id: str,
        attempt_number: int,
    ) -> ExecutionResult:
        limits = limits_from_contract_seconds(contract.max_execution_seconds)
        network_policy = policy_from_contract(contract.requires_network, contract.allowed_domains)

        workspace_dir = Path(tempfile.mkdtemp(prefix="sandbox_"))
        try:
            (workspace_dir / SCRIPT_FILENAME).write_text(code)
            os.chmod(workspace_dir, 0o777)

            result = self._execute(workspace_dir, limits, network_policy)

            if contract.expects_artifacts():
                artifact_paths = persist_expected_artifacts(
                    workspace_dir, contract.artifacts, session_id, attempt_number
                )
            else:
                artifact_paths = persist_all_output_files(workspace_dir, session_id, attempt_number)

            result.artifact_paths = artifact_paths
            return result
        finally:
            shutil.rmtree(workspace_dir, ignore_errors=True)

    def _execute(
        self,
        workspace_dir: Path,
        limits: ResourceLimits,
        network_policy: NetworkPolicy,
    ) -> ExecutionResult:
        container_name = f"sandbox-{uuid.uuid4().hex[:12]}"
        start_time = time.monotonic()

        container_kwargs: dict = dict(
            image=SANDBOX_IMAGE_NAME,
            name=container_name,
            command=["python", SCRIPT_FILENAME],
            working_dir="/workspace",
            volumes={str(workspace_dir): {"bind": "/workspace", "mode": "rw"}},
            mem_limit=limits.memory_bytes,
            nano_cpus=limits.nano_cpus,
            pids_limit=limits.pids_limit,
            network_mode=network_policy.docker_network_mode(),
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            detach=True,
        )
        if SANDBOX_RUNTIME:
            container_kwargs["runtime"] = SANDBOX_RUNTIME

        container = self._client.containers.run(**container_kwargs)

        timed_out = False
        exit_code: int | None = None

        try:
            while True:
                container.reload()
                if container.status == "exited":
                    exit_code = container.attrs["State"]["ExitCode"]
                    break
                if time.monotonic() - start_time > limits.timeout_seconds:
                    timed_out = True
                    container.kill()
                    break
                time.sleep(POLL_INTERVAL_SECONDS)

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        finally:
            try:
                container.remove(force=True)
            except NotFound:
                pass

        duration = time.monotonic() - start_time

        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_seconds=duration,
            artifact_paths=[],
        )
