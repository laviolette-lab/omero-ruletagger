import re


class _LogicalOperator:
    """Handles logical operations for the autotagger."""

    OPERATIONS = {
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "eq": lambda a, b: a == b,
        "ge": lambda a, b: a >= b,
        "le": lambda a, b: a <= b,
        "ne": lambda a, b: a != b,
        "match": lambda a, b: re.match(b, a) is not None,
        "always": lambda a, b: True,
        "never": lambda a, b: False,
    }

    @classmethod
    def apply(cls, operation: str, a, b, invert=False) -> bool:
        """
        Applies the logical operation to the two values.
        Inverts logic if required.
        """
        a = cls.ensure_unwrapped(a)
        applies = cls.OPERATIONS[operation](a, b)
        return not applies if invert else applies

    @staticmethod
    def ensure_unwrapped(val):
        if hasattr(val, "getValue"):
            return val.getValue()
        return val


LogicalOperator = _LogicalOperator
