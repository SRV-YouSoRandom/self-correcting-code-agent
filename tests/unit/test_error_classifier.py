from __future__ import annotations

from agent.core.errors.classifier import (
    classify_contract_failure,
    classify_execution_failure,
    classify_semantic_failure,
)
from agent.core.errors.taxonomy import ErrorCategory, RepairStrategy
from agent.core.state import ExecutionResult


def _traceback(exception_line: str) -> str:
    return (
        "Traceback (most recent call last):\n"
        '  File "script.py", line 1, in <module>\n'
        f"{exception_line}\n"
    )


def test_module_not_found_classified_as_environment_patch() -> None:
    result = ExecutionResult(
        exit_code=1,
        stderr=_traceback("ModuleNotFoundError: No module named 'requests_html'"),
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.ENVIRONMENT
    assert classification.repair_strategy == RepairStrategy.PATCH
    assert classification.exception_name == "ModuleNotFoundError"


def test_syntax_error_classified_as_syntax_patch() -> None:
    result = ExecutionResult(
        exit_code=1,
        stderr=_traceback("SyntaxError: invalid syntax"),
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.SYNTAX
    assert classification.repair_strategy == RepairStrategy.PATCH


def test_key_error_classified_as_runtime_patch() -> None:
    result = ExecutionResult(
        exit_code=1,
        stderr=_traceback("KeyError: 'missing_key'"),
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.RUNTIME
    assert classification.repair_strategy == RepairStrategy.PATCH


def test_timeout_flag_classified_as_resource_rethink() -> None:
    result = ExecutionResult(exit_code=None, timed_out=True)
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.RESOURCE
    assert classification.repair_strategy == RepairStrategy.RETHINK
    assert classification.exception_name == "TimeoutError"


def test_memory_error_classified_as_resource_rethink() -> None:
    result = ExecutionResult(
        exit_code=1,
        stderr=_traceback("MemoryError"),
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.RESOURCE
    assert classification.repair_strategy == RepairStrategy.RETHINK


def test_http_403_in_output_classified_as_external_rethink() -> None:
    result = ExecutionResult(
        exit_code=1,
        stdout="Response status: 403 Forbidden",
        stderr=_traceback("Exception: request failed"),
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.EXTERNAL
    assert classification.repair_strategy == RepairStrategy.RETHINK
    assert classification.http_status == 403


def test_http_status_takes_priority_over_generic_exception() -> None:
    result = ExecutionResult(
        exit_code=1,
        stdout="429 Too Many Requests",
        stderr=_traceback("ConnectionError: rate limited"),
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.EXTERNAL
    assert classification.http_status == 429


def test_resource_keyword_without_exception_classified_as_resource() -> None:
    result = ExecutionResult(
        exit_code=137,
        stderr="Process killed: out of memory",
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.RESOURCE


def test_unrecognized_exception_falls_back_to_unknown() -> None:
    result = ExecutionResult(
        exit_code=1,
        stderr=_traceback("SomeCustomLibraryError: something odd happened"),
    )
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.UNKNOWN
    assert classification.repair_strategy == RepairStrategy.PATCH


def test_no_traceback_but_nonzero_exit_classified_as_runtime() -> None:
    result = ExecutionResult(exit_code=1, stderr="")
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.RUNTIME


def test_clean_exit_with_no_error_signal_classified_as_unknown() -> None:
    result = ExecutionResult(exit_code=0, stderr="")
    classification = classify_execution_failure(result)

    assert classification.category == ErrorCategory.UNKNOWN


def test_classify_semantic_failure_is_rethink() -> None:
    classification = classify_semantic_failure("Output did not match user intent.")

    assert classification.category == ErrorCategory.SEMANTIC
    assert classification.repair_strategy == RepairStrategy.RETHINK
    assert classification.exception_name is None
    assert classification.truncated_traceback == "Output did not match user intent."


def test_classify_contract_failure_is_patch() -> None:
    classification = classify_contract_failure("Artifact too small.")

    assert classification.category == ErrorCategory.CONTRACT
    assert classification.repair_strategy == RepairStrategy.PATCH
    assert classification.exception_name is None


def test_long_traceback_is_truncated() -> None:
    long_lines = "\n".join(f"  line {i}" for i in range(100))
    stderr = f"Traceback (most recent call last):\n{long_lines}\nValueError: too long"
    result = ExecutionResult(exit_code=1, stderr=stderr)

    classification = classify_execution_failure(result)

    assert "omitted" in classification.truncated_traceback
    assert len(classification.truncated_traceback.splitlines()) < 100
