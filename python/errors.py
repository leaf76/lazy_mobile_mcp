from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkerError(Exception):
    message: str
    code: str
    category: str
    trace_id: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def error_response(error: WorkerError) -> dict[str, str]:
    return {
        "error": error.message,
        "code": error.code,
        "trace_id": error.trace_id,
    }
