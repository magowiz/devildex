# tests/dummy_project/module1.py
"""A dummy module for testing."""


def a_simple_function() -> str:
    """Do nothing a_simple_function.

    It doesn't do much!
    """
    return "Hello from dummy module1!"


class AnotherSimpleClass:
    """AnotherSimpleClass.

    It's also quite simple.
    """

    def __init__(self, name: str = "World") -> None:
        """Initialize the class."""
        self.name = name

    def greet(self) -> str:
        """Greets someone."""
        return f"Hello, {self.name}, from AnotherSimpleClass!"
