from enum import Enum


class ErrorCategory(str, Enum):
    ENVIRONMENT = "environment"
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    RESOURCE = "resource"
    EXTERNAL = "external"
    SEMANTIC = "semantic"
    UNKNOWN = "unknown"


class RepairStrategy(str, Enum):
    PATCH = "patch"
    RETHINK = "rethink"


CATEGORY_REPAIR_STRATEGY: dict[ErrorCategory, RepairStrategy] = {
    ErrorCategory.ENVIRONMENT: RepairStrategy.PATCH,
    ErrorCategory.SYNTAX: RepairStrategy.PATCH,
    ErrorCategory.RUNTIME: RepairStrategy.PATCH,
    ErrorCategory.RESOURCE: RepairStrategy.RETHINK,
    ErrorCategory.EXTERNAL: RepairStrategy.RETHINK,
    ErrorCategory.SEMANTIC: RepairStrategy.RETHINK,
    ErrorCategory.UNKNOWN: RepairStrategy.PATCH,
}

EXCEPTION_CATEGORY_MAP: dict[str, ErrorCategory] = {
    "ModuleNotFoundError": ErrorCategory.ENVIRONMENT,
    "ImportError": ErrorCategory.ENVIRONMENT,
    "FileNotFoundError": ErrorCategory.ENVIRONMENT,
    "SyntaxError": ErrorCategory.SYNTAX,
    "IndentationError": ErrorCategory.SYNTAX,
    "TabError": ErrorCategory.SYNTAX,
    "TypeError": ErrorCategory.RUNTIME,
    "ValueError": ErrorCategory.RUNTIME,
    "KeyError": ErrorCategory.RUNTIME,
    "IndexError": ErrorCategory.RUNTIME,
    "AttributeError": ErrorCategory.RUNTIME,
    "ZeroDivisionError": ErrorCategory.RUNTIME,
    "NameError": ErrorCategory.RUNTIME,
    "UnboundLocalError": ErrorCategory.RUNTIME,
    "MemoryError": ErrorCategory.RESOURCE,
    "RecursionError": ErrorCategory.RESOURCE,
    "TimeoutError": ErrorCategory.RESOURCE,
    "ConnectionError": ErrorCategory.EXTERNAL,
    "ConnectionRefusedError": ErrorCategory.EXTERNAL,
    "ConnectionResetError": ErrorCategory.EXTERNAL,
    "HTTPError": ErrorCategory.EXTERNAL,
    "URLError": ErrorCategory.EXTERNAL,
    "SSLError": ErrorCategory.EXTERNAL,
}

RESOURCE_SIGNAL_KEYWORDS: tuple[str, ...] = (
    "timed out",
    "timeout",
    "killed",
    "oom",
    "out of memory",
    "resource temporarily unavailable",
)

EXTERNAL_HTTP_STATUS_SIGNALS: tuple[int, ...] = (403, 404, 407, 408, 409, 429, 500, 502, 503, 504)


def repair_strategy_for(category: ErrorCategory) -> RepairStrategy:
    return CATEGORY_REPAIR_STRATEGY.get(category, RepairStrategy.PATCH)


def category_for_exception_name(exception_name: str) -> ErrorCategory:
    return EXCEPTION_CATEGORY_MAP.get(exception_name, ErrorCategory.UNKNOWN)