from __future__ import annotations

import re
from dataclasses import dataclass, field

from agent.core.errors.taxonomy import EXTERNAL_HTTP_STATUS_SIGNALS, RESOURCE_SIGNAL_KEYWORDS

_TRACEBACK_HEADER_RE = re.compile(r"^Traceback \(most recent call last\):", re.MULTILINE)
_FRAME_LINE_RE = re.compile(r'^\s*File "(?P<file>.+?)", line (?P<line>\d+), in (?P<func>.+)$', re.MULTILINE)
_EXCEPTION_LINE_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning))(?::\s*(?P<message>.*))?$", re.MULTILINE)
_HTTP_STATUS_RE = re.compile(r"\b(4\d{2}|5\d{2})\b")

DEFAULT_MAX_TRACEBACK_LINES = 30


@dataclass
class ParsedFrame:
    file: str
    line: int
    function: str


@dataclass
class ParsedTraceback:
    exception_name: str | None = None
    exception_message: str = ""
    frames: list[ParsedFrame] = field(default_factory=list)
    http_status: int | None = None
    resource_signal_detected: bool = False
    truncated_text: str = ""

    @property
    def last_frame(self) -> ParsedFrame | None:
        return self.frames[-1] if self.frames else None


def _extract_frames(text: str) -> list[ParsedFrame]:
    frames: list[ParsedFrame] = []
    for match in _FRAME_LINE_RE.finditer(text):
        frames.append(
            ParsedFrame(
                file=match.group("file"),
                line=int(match.group("line")),
                function=match.group("func"),
            )
        )
    return frames


def _extract_exception(text: str) -> tuple[str | None, str]:
    matches = list(_EXCEPTION_LINE_RE.finditer(text))
    if not matches:
        return None, ""
    last = matches[-1]
    return last.group("name"), (last.group("message") or "").strip()


def _extract_http_status(text: str) -> int | None:
    for match in _HTTP_STATUS_RE.finditer(text):
        code = int(match.group(1))
        if code in EXTERNAL_HTTP_STATUS_SIGNALS:
            return code
    return None


def _detect_resource_signal(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in RESOURCE_SIGNAL_KEYWORDS)


def truncate_traceback(text: str, max_lines: int = DEFAULT_MAX_TRACEBACK_LINES) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    head = lines[:5]
    tail = lines[-(max_lines - 5):]
    omitted = len(lines) - len(head) - len(tail)
    return "\n".join(head + [f"... ({omitted} lines omitted) ..."] + tail)


def parse_traceback(stderr: str, stdout: str = "", max_lines: int = DEFAULT_MAX_TRACEBACK_LINES) -> ParsedTraceback:
    combined = f"{stderr}\n{stdout}"
    exception_name, exception_message = _extract_exception(stderr)
    frames = _extract_frames(stderr)
    http_status = _extract_http_status(combined)
    resource_signal = _detect_resource_signal(combined)
    truncated = truncate_traceback(stderr, max_lines) if stderr.strip() else ""

    return ParsedTraceback(
        exception_name=exception_name,
        exception_message=exception_message,
        frames=frames,
        http_status=http_status,
        resource_signal_detected=resource_signal,
        truncated_text=truncated,
    )