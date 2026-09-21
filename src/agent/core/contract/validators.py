from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from PIL import Image

from agent.core.contract.schema import ArtifactExpectations, ArtifactType, ExecutionContract
from agent.core.state import EvaluationLayer, EvaluationResult, ExecutionResult

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"


def validate_execution_layer(execution_result: ExecutionResult) -> EvaluationResult:
    if execution_result.timed_out:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.EXECUTION,
            reason="Execution exceeded the allotted time limit.",
        )
    if execution_result.exit_code != 0:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.EXECUTION,
            reason=f"Process exited with non-zero code {execution_result.exit_code}.",
        )
    return EvaluationResult(passed=True)


def validate_contract_layer(
    contract: ExecutionContract,
    execution_result: ExecutionResult,
) -> EvaluationResult:
    if not contract.expects_artifacts():
        return EvaluationResult(passed=True)

    persisted_by_name = {Path(path).name: Path(path) for path in execution_result.artifact_paths}

    for expectation in contract.artifacts:
        artifact_path = persisted_by_name.get(expectation.filename)
        if artifact_path is None or not artifact_path.exists():
            return EvaluationResult(
                passed=False,
                failed_layer=EvaluationLayer.CONTRACT,
                reason=f"Expected artifact '{expectation.filename}' was not produced.",
            )

        result = _validate_single_artifact(artifact_path, expectation)
        if not result.passed:
            return result

    return EvaluationResult(passed=True)


def _validate_single_artifact(path: Path, expectation: ArtifactExpectations) -> EvaluationResult:
    size = path.stat().st_size
    if size < expectation.min_size_bytes:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.CONTRACT,
            reason=f"Artifact '{expectation.filename}' is only {size} bytes, expected at least {expectation.min_size_bytes}.",
        )

    if expectation.artifact_type == ArtifactType.PNG:
        return _validate_image(path, expectation, PNG_MAGIC)
    if expectation.artifact_type == ArtifactType.JPEG:
        return _validate_image(path, expectation, JPEG_MAGIC)
    if expectation.artifact_type == ArtifactType.CSV:
        return _validate_csv(path, expectation)
    if expectation.artifact_type == ArtifactType.JSON:
        return _validate_json(path, expectation)

    return EvaluationResult(passed=True)


def _validate_image(path: Path, expectation: ArtifactExpectations, magic: bytes) -> EvaluationResult:
    header = path.read_bytes()[: len(magic)]
    if header != magic:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.CONTRACT,
            reason=f"Artifact '{expectation.filename}' does not have the expected file signature for {expectation.artifact_type.value}.",
        )

    if expectation.min_pixel_variance is not None:
        try:
            with Image.open(path) as image:
                grayscale = image.convert("L")
                pixels = list(grayscale.getdata())
        except Exception as exc:
            return EvaluationResult(
                passed=False,
                failed_layer=EvaluationLayer.CONTRACT,
                reason=f"Artifact '{expectation.filename}' could not be opened as an image: {exc}",
            )

        variance = statistics.pvariance(pixels) if len(pixels) > 1 else 0.0
        if variance < expectation.min_pixel_variance:
            return EvaluationResult(
                passed=False,
                failed_layer=EvaluationLayer.CONTRACT,
                reason=f"Artifact '{expectation.filename}' has pixel variance {variance:.2f}, below minimum {expectation.min_pixel_variance}. It may be blank.",
            )

    return EvaluationResult(passed=True)


def _validate_csv(path: Path, expectation: ArtifactExpectations) -> EvaluationResult:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            rows = list(reader)
    except Exception as exc:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.CONTRACT,
            reason=f"Artifact '{expectation.filename}' could not be parsed as CSV: {exc}",
        )

    if not rows:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.CONTRACT,
            reason=f"Artifact '{expectation.filename}' is an empty CSV.",
        )

    header = rows[0]
    if expectation.expected_columns:
        missing = [col for col in expectation.expected_columns if col not in header]
        if missing:
            return EvaluationResult(
                passed=False,
                failed_layer=EvaluationLayer.CONTRACT,
                reason=f"Artifact '{expectation.filename}' is missing expected columns: {missing}.",
            )

    data_row_count = len(rows) - 1
    if expectation.min_rows is not None and data_row_count < expectation.min_rows:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.CONTRACT,
            reason=f"Artifact '{expectation.filename}' has {data_row_count} data rows, expected at least {expectation.min_rows}.",
        )

    return EvaluationResult(passed=True)


def _validate_json(path: Path, expectation: ArtifactExpectations) -> EvaluationResult:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.CONTRACT,
            reason=f"Artifact '{expectation.filename}' could not be parsed as JSON: {exc}",
        )

    if content in (None, [], {}, ""):
        return EvaluationResult(
            passed=False,
            failed_layer=EvaluationLayer.CONTRACT,
            reason=f"Artifact '{expectation.filename}' is empty JSON.",
        )

    if expectation.min_rows is not None and isinstance(content, list):
        if len(content) < expectation.min_rows:
            return EvaluationResult(
                passed=False,
                failed_layer=EvaluationLayer.CONTRACT,
                reason=f"Artifact '{expectation.filename}' has {len(content)} items, expected at least {expectation.min_rows}.",
            )

    return EvaluationResult(passed=True)
