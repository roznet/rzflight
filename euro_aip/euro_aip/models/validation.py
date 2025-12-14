"""
Validation module for EuroAipModel.

This module provides validation functionality for model operations,
including validation results and custom validation hooks.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ValidationError:
    """Represents a single validation error."""

    field: str
    message: str
    value: Any = None

    def __str__(self) -> str:
        if self.value is not None:
            return f"{self.field}: {self.message} (value: {self.value})"
        return f"{self.field}: {self.message}"


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.warnings) > 0

    def add_error(self, field: str, message: str, value: Any = None) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(field, message, value))

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)

    @classmethod
    def success(cls) -> 'ValidationResult':
        """Create a successful validation result."""
        return cls(errors=[])

    @classmethod
    def error(cls, field: str, message: str, value: Any = None) -> 'ValidationResult':
        """Create a validation result with a single error."""
        return cls(errors=[ValidationError(field, message, value)])

    def __str__(self) -> str:
        if self.is_valid:
            if self.has_warnings:
                return f"Valid (with {len(self.warnings)} warnings)"
            return "Valid"
        return f"Invalid ({len(self.errors)} errors)"

    def get_error_messages(self) -> List[str]:
        """Get all error messages as strings."""
        return [str(error) for error in self.errors]


class ModelValidationError(Exception):
    """Exception raised when model validation fails."""

    def __init__(self, message: str, validation_result: Optional[ValidationResult] = None, details: Any = None):
        """
        Initialize validation error.

        Args:
            message: Error message
            validation_result: Optional ValidationResult with details
            details: Optional additional details
        """
        super().__init__(message)
        self.validation_result = validation_result
        self.details = details

    def __str__(self) -> str:
        if self.validation_result:
            error_messages = "\n  - ".join(self.validation_result.get_error_messages())
            return f"{super().__str__()}\nErrors:\n  - {error_messages}"
        return super().__str__()
