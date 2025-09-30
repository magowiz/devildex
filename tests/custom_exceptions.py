"""custom exceptions for tests module."""

from json import JSONDecodeError
from typing import ClassVar


class CustomDecodeJsonError(JSONDecodeError):
    """Custom Json Decode Error."""

    def __init__(self, data: str, index: int) -> None:
        """Construct Custom Json Decode Error."""
        super().__init__("JSON Decode Error", data, index)


class CustomAssertionError(AssertionError):
    """Custom Assertion Error."""

    excs: ClassVar = {
        "CANT_CONNECT": (
            "Client could not connect to server within"
            " {max_wait} seconds. "
            "Last exception: {last_exception}"
        )
    }

    def __init__(self, error_type: str, **kwargs: dict) -> None:
        """Construct Custom Assertion Error."""
        msg = "generic assertion exception"
        if error_type in self.excs:
            msg = self.excs["type"].format(kwargs)
        super().__init__(msg)
