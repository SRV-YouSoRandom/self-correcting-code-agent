from __future__ import annotations

import os
import shutil
from pathlib import Path

from agent.core.contract.schema import ArtifactExpectations

ARTIFACTS_BASE_DIR = Path(os.environ.get("SANDBOX_ARTIFACTS_DIR", "/tmp/agent-artifacts"))
EXCLUDED_FILENAMES = ("script.py",)


def persist_expected_artifacts(
    workspace_dir: Path,
    expectations: list[ArtifactExpectations],
    session_id: str,
    attempt_number: int,
) -> list[str]:
    dest_dir = ARTIFACTS_BASE_DIR / session_id / str(attempt_number)
    dest_dir.mkdir(parents=True, exist_ok=True)

    persisted: list[str] = []
    for expectation in expectations:
        source = workspace_dir / expectation.filename
        if source.exists() and source.is_file():
            destination = dest_dir / expectation.filename
            shutil.copy2(source, destination)
            persisted.append(str(destination))
    return persisted


def persist_all_output_files(
    workspace_dir: Path,
    session_id: str,
    attempt_number: int,
) -> list[str]:
    dest_dir = ARTIFACTS_BASE_DIR / session_id / str(attempt_number)
    dest_dir.mkdir(parents=True, exist_ok=True)

    persisted: list[str] = []
    for path in workspace_dir.iterdir():
        if path.is_file() and path.name not in EXCLUDED_FILENAMES:
            destination = dest_dir / path.name
            shutil.copy2(path, destination)
            persisted.append(str(destination))
    return persisted
