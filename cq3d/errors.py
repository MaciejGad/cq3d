from __future__ import annotations


class Cq3dError(Exception):
    """Base class for user-facing DSL errors."""

    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        if self.line is None:
            return self.message
        return f"line {self.line}: {self.message}"


class ParseError(Cq3dError):
    """Raised when the source text cannot be parsed."""


class ValidationError(Cq3dError):
    """Raised when the AST is semantically invalid."""


class BackendError(Cq3dError):
    """Raised when geometry generation fails."""
