from inspect import signature
from typing import Callable, Union

import inflect

from omero.gateway import BlitzObjectWrapper


class OmeroGetter:
    def __init__(self):
        self._ie = inflect.engine()

    def _ensure_singular(self, word: str) -> str:
        """Ensures the word is singular.

        Parameters
        ----------
        word : str
            Word to ensure is singular.

        Returns
        -------
        str
            Singular form of the word.
        """
        singular = self._ie.singular_noun(word)
        return singular if singular is not False else word

    def _ensure_plural(self, word: str) -> str:
        """Ensures the word is plural.

        Parameters
        ----------
        word : str
            Word to ensure is plural.

        Returns
        -------
        str
            Plural form of the word.
        """
        plural = self._ie.plural_noun(word)
        return plural if plural is not False else word

    def _unwrap_function(self, obj, getter, name) -> Callable:
        """
        BlitzWrappers will use a wrap function if a function belongs to the underlying object.
        This wrapped function is bound to the given object, exactly what we don't want.
        It checks if it's a wrapped function and if so unwraps and rewalks.
        Otherwise it will return the original function.
        """
        if getter is None:
            return getter
        if getter.__name__ == "wrap":
            if obj._obj is None:  # pylint: disable=protected-access
                raise ValueError("Model object is None! (Should not happen)")

            return self.get_getter(obj._obj, name)  # pylint: disable=protected-access

        return getter

    def _check_args(self, getter):
        """Checks if the getter has the correct number of arguments."""
        if getter is None:
            return None
        sig = signature(getter)
        params = sig.parameters
        for param in params:
            if param != "self" and params[param].default == params[param].empty:
                return getter
        return None

    def _get_getter(self, obj: BlitzObjectWrapper, attr_name: str) -> Callable:
        """Gets the getter function for a child object.
        Prioritizes get{attr_name} over list{attr_name}.
        Prioritizes raw attr_name last.

        Parameters
        ----------
        obj : BlitzObjectWrapper
            Parent object to get the getter from.
        name : str
            Name of the child object to get.

        Returns
        -------
        function
            Getter function for the child object.
        """
        getter = None
        attr_name = attr_name.lower()
        for attr in dir(obj):
            if attr.lower() == f"get{attr_name}":
                getter = getattr(obj, attr)
                break
            if attr.lower() == f"list{attr_name}":
                getter = getattr(obj, attr)
                break
            if attr.lower() == f"_get{attr_name}":
                getter = getattr(obj, attr)
                break
            if attr.lower() == f"_list{attr_name}":
                getter = getattr(obj, attr)
                break
        return getter.__func__ if getter is not None else None

    def get_getter(
        self, parent: BlitzObjectWrapper, child: Union[str, int]
    ) -> Callable:
        """Walks the omero object model to get the getter for a child object.
        Case insensitive, due to camelCase naming conventions making
        splitting the name into words difficult. (snake_case is better smh)

        Parameters
        ----------
        parent : BlitzObjectWrapper
            Parent omero object.
        child : str
            Type of child object to get.

        Returns
        -------
        function
            Getter function for the child object.
        """
        if isinstance(child, int):  # integers are used to index lists
            return child

        assert isinstance(child, str)
        if child.lower() == "count":  # count is a keyword
            return "count"

        # try the plural form first (so we don't have to index)
        plural = self._ensure_plural(child)
        getter = self._get_getter(parent, plural)

        # if that fails, try the singular form
        if getter is None:
            singular = self._ensure_singular(child)
            getter = self._get_getter(parent, singular)

        # need to unwrap the function if it's a wrapped function
        getter = self._unwrap_function(parent, getter, child)

        # avoid functions that require arguments
        arg_getter = self._check_args(getter)
        if arg_getter is not None:
            getter = None

        # last ditch effort, try to get the getter from the underlying object
        if getter is None and hasattr(parent, "_obj"):
            getter = self.get_getter(
                parent._obj, child  # pylint: disable=protected-access
            )

        if getter is None:
            raise ValueError(f"Could not find getter for child: {child}")

        return getter
