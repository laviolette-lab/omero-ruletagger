"""
A class for handling logical operations in the autotagger.

This class provides a collection of logical operations for comparing values and 
evaluating conditions. It includes standard comparison operators as well as
pattern matching and constant true/false operations.
"""

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
        """Ensures a value is unwrapped from OMERO wrapper objects if necessary.

        Parameters
        ----------
        val : object
            The value to unwrap. Can be either a wrapped OMERO object with getValue() method
            or a regular Python object.

        Returns
        -------
        object
            The unwrapped value. If input has getValue() method, returns result of getValue(),
            otherwise returns the input unchanged.

        Notes
        -----
        OMERO often wraps primitive values in wrapper objects that require getValue()
        to access the actual value. This helper method safely unwraps such objects.
        """
        if hasattr(val, "getValue"):
            return val.getValue()
        return val


LogicalOperator = _LogicalOperator
