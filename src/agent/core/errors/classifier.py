from __future__ import annotations

from agent.core.errors.taxonomy import ErrorCategory, category_for_exception_name, repair_strategy_for
from agent.core.errors.traceback_parser import ParsedTraceback, parse_traceback
from agent.core.state import ErrorClassification, ExecutionResult


def classify_execution_failure(execution_result: ExecutionResult) -> ErrorClassification:
    if execution_result.timed_out:
        return ErrorClassification(
            category=ErrorCategory.RESOURCE,
            repair_strategy=repair_strategy_for(ErrorCategory.RESOURCE),
            exception_name="TimeoutError",
            truncated_traceback="Execution exceeded the allotted time limit.",
        )

    parsed = parse_traceback(execution_result.stderr, execution_result.stdout)

    if parsed.http_status is not None:
        category = ErrorCategory.EXTERNAL
        return ErrorClassification(
            category=category,
            repair_strategy=repair_strategy_for(category),
            exception_name=parsed.exception_name,
            http_status=parsed.http_status,
            truncated_traceback=parsed.truncated_text,
        )

    if parsed.resource_signal_detected:
        category = ErrorCategory.RESOURCE
        return ErrorClassification(
            category=category,
            repair_strategy=repair_strategy_for(category),
            exception_name=parsed.exception_name,
            truncated_traceback=parsed.truncated_text,
        )

    category = _category_from_parsed(parsed, execution_result.exit_code)

    return ErrorClassification(
        category=category,
        repair_strategy=repair_strategy_for(category),
        exception_name=parsed.exception_name,
        truncated_traceback=parsed.truncated_text,
    )


def _category_from_parsed(parsed: ParsedTraceback, exit_code: int | None) -> ErrorCategory:
    if parsed.exception_name is not None:
        return category_for_exception_name(parsed.exception_name)
    if exit_code not in (None, 0):
        return ErrorCategory.RUNTIME
    return ErrorCategory.UNKNOWN


def classify_semantic_failure(reason: str) -> ErrorClassification:
    return ErrorClassification(
        category=ErrorCategory.SEMANTIC,
        repair_strategy=repair_strategy_for(ErrorCategory.SEMANTIC),
        exception_name=None,
        truncated_traceback=reason,
    )