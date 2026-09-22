from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from agent.core.contract.schema import ArtifactExpectations, ArtifactType, ExecutionContract
from agent.core.contract.validators import validate_contract_layer, validate_execution_layer
from agent.core.state import EvaluationLayer, ExecutionResult


def test_execution_layer_passes_on_clean_exit() -> None:
    result = ExecutionResult(exit_code=0)
    evaluation = validate_execution_layer(result)

    assert evaluation.passed is True


def test_execution_layer_fails_on_nonzero_exit() -> None:
    result = ExecutionResult(exit_code=1)
    evaluation = validate_execution_layer(result)

    assert evaluation.passed is False
    assert evaluation.failed_layer == EvaluationLayer.EXECUTION


def test_execution_layer_fails_on_timeout() -> None:
    result = ExecutionResult(exit_code=None, timed_out=True)
    evaluation = validate_execution_layer(result)

    assert evaluation.passed is False
    assert "time limit" in evaluation.reason


def test_contract_layer_passes_when_no_artifacts_expected() -> None:
    contract = ExecutionContract(intent_summary="print something")
    result = ExecutionResult(exit_code=0)

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is True


def test_contract_layer_fails_when_expected_artifact_missing(tmp_path: Path) -> None:
    contract = ExecutionContract(
        intent_summary="write a csv",
        artifacts=[ArtifactExpectations(artifact_type=ArtifactType.CSV, filename="out.csv")],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is False
    assert "was not produced" in evaluation.reason


def test_contract_layer_fails_when_artifact_too_small(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.csv"
    artifact_path.write_text("a")

    contract = ExecutionContract(
        intent_summary="write a csv",
        artifacts=[
            ArtifactExpectations(artifact_type=ArtifactType.CSV, filename="out.csv", min_size_byte=100)
        ],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is False
    assert "bytes" in evaluation.reason


def test_csv_validation_passes_with_matching_columns_and_rows(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.csv"
    artifact_path.write_text("name,age\nAlice,30\nBob,25\n")

    contract = ExecutionContract(
        intent_summary="write a csv",
        artifacts=[
            ArtifactExpectations(
                artifact_type=ArtifactType.CSV,
                filename="out.csv",
                expected_columns=["name", "age"],
                min_row=2,
            )
        ],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is True


def test_csv_validation_fails_on_missing_columns(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.csv"
    artifact_path.write_text("name\nAlice\n")

    contract = ExecutionContract(
        intent_summary="write a csv",
        artifacts=[
            ArtifactExpectations(
                artifact_type=ArtifactType.CSV,
                filename="out.csv",
                expected_columns=["name", "age"],
            )
        ],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is False
    assert "missing expected columns" in evaluation.reason


def test_csv_validation_fails_on_insufficient_rows(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.csv"
    artifact_path.write_text("name,age\nAlice,30\n")

    contract = ExecutionContract(
        intent_summary="write a csv",
        artifacts=[
            ArtifactExpectations(
                artifact_type=ArtifactType.CSV,
                filename="out.csv",
                min_row=5,
            )
        ],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is False
    assert "data rows" in evaluation.reason


def test_png_validation_fails_on_wrong_magic_bytes(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.png"
    artifact_path.write_bytes(b"not a real png" * 10)

    contract = ExecutionContract(
        intent_summary="make a chart",
        artifacts=[ArtifactExpectations(artifact_type=ArtifactType.PNG, filename="out.png")],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is False
    assert "file signature" in evaluation.reason


def test_png_validation_fails_on_blank_image_low_variance(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.png"
    blank_image = Image.new("RGB", (100, 100), color=(255, 255, 255))
    blank_image.save(artifact_path, format="PNG")

    contract = ExecutionContract(
        intent_summary="make a chart",
        artifacts=[
            ArtifactExpectations(
                artifact_type=ArtifactType.PNG,
                filename="out.png",
                min_pixel_variance=10.0,
            )
        ],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is False
    assert "blank" in evaluation.reason


def test_png_validation_passes_on_varied_image(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.png"
    varied_image = Image.new("RGB", (100, 100))
    pixels = varied_image.load()
    for x in range(100):
        for y in range(100):
            pixels[x, y] = (x * 2 % 256, y * 2 % 256, (x + y) % 256)
    varied_image.save(artifact_path, format="PNG")

    contract = ExecutionContract(
        intent_summary="make a chart",
        artifacts=[
            ArtifactExpectations(
                artifact_type=ArtifactType.PNG,
                filename="out.png",
                min_pixel_variance=10.0,
            )
        ],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is True


def test_json_validation_fails_on_empty_content(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.json"
    artifact_path.write_text("[]")

    contract = ExecutionContract(
        intent_summary="write json",
        artifacts=[ArtifactExpectations(artifact_type=ArtifactType.JSON, filename="out.json")],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is False
    assert "empty" in evaluation.reason


def test_json_validation_passes_on_valid_list(tmp_path: Path) -> None:
    artifact_path = tmp_path / "out.json"
    artifact_path.write_text('[{"a": 1}, {"a": 2}]')

    contract = ExecutionContract(
        intent_summary="write json",
        artifacts=[
            ArtifactExpectations(artifact_type=ArtifactType.JSON, filename="out.json", min_row=2)
        ],
    )
    result = ExecutionResult(exit_code=0, artifact_paths=[str(artifact_path)])

    evaluation = validate_contract_layer(contract, result)

    assert evaluation.passed is True
