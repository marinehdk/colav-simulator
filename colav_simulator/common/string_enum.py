"""Python 3.10-compatible string enum with :class:`StrEnum` semantics."""

from enum import Enum


class StringEnum(str, Enum):
    """String-valued enum whose string form is its serialized value."""

    def __str__(self) -> str:
        """Return public string value, matching stdlib StrEnum behavior."""
        return str(self.value)
