"""
Compiles a schema into a set of rules for the autotagger.
See rules.yml for an example input and designs/compiled_rules.jsonc for an example output
"""

import re
import copy
import json
import string
import logging
from typing import Iterable

import yaml

from omero.gateway import BlitzGateway, ProjectWrapper, DatasetWrapper, KNOWN_WRAPPERS

from .getter import OmeroGetter
from .logic import LogicalOperator


class Schema0Compiler:  # pylint: disable=too-many-instance-attributes
    """Compiles the original yaml design into the dict defined in designs/compiled_rules.jsonc"""

    BASE_STEP = {"object": "", "getter": None, "rules": [], "children": []}

    def __init__(self, conn: BlitzGateway, tagging_rules: list, strict: bool = True):
        self.conn: BlitzGateway = conn
        self.tagging_rules: list[dict] = tagging_rules
        self.strict: bool = strict

        self.formatter = string.Formatter()

        self.getter = OmeroGetter()

        self._project = next(conn.getObjects("Project"))
        self._dataset = next(conn.getObjects("Dataset"))
        self._image = next(conn.getObjects("Image"))

    @classmethod
    def _format_initial_path(cls):
        """Currently we only support tagging from the first three object levels
        No support for HCS at the moment
        """
        image_step = copy.deepcopy(cls.BASE_STEP)
        image_step["object"] = "Image"
        image_step["getter"] = DatasetWrapper.listChildren

        dataset_step = copy.deepcopy(cls.BASE_STEP)
        dataset_step["object"] = "Dataset"
        dataset_step["getter"] = ProjectWrapper.listChildren
        dataset_step["children"] = [image_step]

        project_step = copy.deepcopy(cls.BASE_STEP)
        project_step["object"] = "Project"
        project_step["getter"] = lambda conn: conn.getObjects("Project")
        project_step["children"] = [dataset_step]

        return project_step

    def _get_next_object(self, parent, getter, name):
        """Gets the next object in the path."""
        # handle count keyword
        if isinstance(getter, str):
            return 0

        # handle list index
        if isinstance(getter, int) and isinstance(parent, Iterable):
            return list(parent)[getter]

        # pixels seem to unload for some reason
        if "pixels" in getter.__name__.lower():
            parent._loadPixels()  # pylint: disable=protected-access

        # ideally should get a child object from the example parent
        obj = getter(parent)
        if isinstance(obj, list):
            obj = obj[0] if len(obj) > 0 else None
        if obj is not None:
            return obj

        # but, if it doesn't exist, we need to get our own
        try:
            obj = next(self.conn.getObjects(name, opts={"limit": 1}))
        except KeyError:
            pass
        if obj:
            return obj

        # some object types cannot be gotten through the gateway
        # so we need to create a dummy object, hopefully a wrapper exists
        # we prefer getObjects, as it has an ObjectI underlying it, often with more methods
        if name in KNOWN_WRAPPERS:
            return KNOWN_WRAPPERS[name]()

        # otherwise, we're out of luck
        # at least until we figure out a comprehensive way of getting dummy objs
        # possible to be a value that not all objects have, like a comment
        # will be caught in _compile_logical_rule and checked to allow it if it's the last step
        raise ValueError(f"Could not get object of type {name}. Sorry!")

    def _ensure_rule_type_exclusivity(self, rule: dict):
        """
        Ensures that each rule dictionary contains keys related to only one type of rule.

        This function checks the provided rule dictionary to ensure that it does not
        contain keys for both regex capture rules and logical rules simultaneously,
        as these are mutually exclusive. If both types of keys are found, a ValueError
        is raised. Otherwise, it will log a warning.

        Parameters
        ----------
        rule : dict
            The rule dictionary to be checked for exclusivity.

        Raises
        ------
        ValueError
            If the rule contains both 'capture' and 'rules' keys.

        Warns
        -----
        Warning
            If the rule contains both 'capture' and 'name' keys.

        Returns
        -------
        None
        """
        if rule.get("capture") and rule.get("rules"):
            raise ValueError(
                f"Regex capture rules and logical rules are mutually exclusive. Rule: {rule}"
            )  # pylint: disable=line-too-long
        if rule.get("capture") and rule.get("name"):
            logging.warning(
                "Rule has both a capture and a name! Name will be ignored. Rule: %s",
                rule,
            )  # pylint: disable=line-too-long
        if rule.get("rules") and rule.get("blacklist"):
            logging.warning(
                "Blacklist will be ignored for logical rules. Rule: %s", rule
            )
        if rule.get("rules") and rule.get("format"):
            logging.warning("Format will be ignored for logical rules. Rule: %s", rule)
        allowed_keys = {
            "capture",
            "blacklist",
            "name",
            "rules",
            "format",
            "type",
            "absolute",
        }
        extra_keys = set(rule.keys()) - allowed_keys
        if extra_keys:
            logging.warning(
                "Rule contains invalid keys: %s. Allowed keys are: %s. Rule: %s",
                extra_keys,
                allowed_keys,
                rule,
            )  # pylint: disable=line-too-long

    def _validate_capture_rule(self, rule: dict):
        """
        Validates a capture rule dictionary.

        This function checks the provided capture rule dictionary to ensure that it
        contains the necessary keys and that the 'capture' key contains a valid regex
        pattern. If the rule is invalid, a ValueError is raised.

        Parameters
        ----------
        rule : dict
            The capture rule dictionary to be validated.

        Raises
        ------
        ValueError
            If the rule is missing the 'capture' key.
            If the 'capture' key contains an invalid regex pattern.

        Returns
        -------
        None
        """
        try:
            compiled = re.compile(rule["capture"])
            if compiled.groups == 0:
                raise ValueError(
                    f"Capture rule must contain at least one capture group. Rule: {rule}"
                )
            if rule.get("format"):
                try:
                    rule["format"].format(*[""] * compiled.groups)
                except IndexError as e:
                    raise ValueError(
                        f"Capture regex doesn't have enough groups for format. Rule: {rule}"
                    ) from e
                if compiled.groups > rule["format"].count("{"):
                    logging.warning(
                        "Capture regex has more groups than format variables. Rule: %s",
                        rule,
                    )
        except re.error as e:
            raise ValueError(
                f"Invalid regex pattern in capture rule. Rule: {rule}"
            ) from e

    def compile_capture_rule(self, rule: dict):
        """
        Compiles a capture rule dictionary into a format suitable for the autotagger.

        This function compiles the provided capture rule dictionary into a format suitable
        for the autotagger. The compiled rule will contain the 'capture' key with the compiled
        regex pattern, and the 'format' key with the format string if it is present in the
        original rule. If the 'format' key is not present, it will be set to None.

        Parameters
        ----------
        rule : dict
            The capture rule dictionary to be compiled.

        Returns
        -------
        dict
            The compiled capture rule dictionary.
        """
        regex = re.compile(rule["capture"])
        compiled = {
            "capture": regex,
            "format": rule.get("format", None),
            "blacklist": rule.get("blacklist", []),
            "include_extension": rule.get("include_extension", False),
            "objects": [
                "image"  # this version of the schema only supports capturing image names
            ],
        }
        return compiled

    def _validate_logical_rule(self, rule: dict):
        """
        Validates a logical rule.

        Args:
            rule (dict): The logical rule to validate. It should be a dictionary
                         containing the necessary keys and values that define the rule.

        Raises:
            ValueError: If the rule is not valid according to the expected structure
                        or content.
        """
        # ensure all conditions have the same root object, legal conditions, and all required fields
        root_object = None
        if "name" not in rule:
            raise ValueError(f"Logical tag rule is missing name! Rule: {rule}")
        allowed_keys = {"attribute_path", "operation", "value", "invert"}
        for condition in rule["rules"]:
            # ensure all conditions have the same root object
            defined_root_object = condition["attribute_path"][0]
            if root_object is None:
                root_object = defined_root_object
            if root_object != defined_root_object:
                raise ValueError(
                    f"Logical tag rule has multiple root objects! Use parent or child attributes to climb up or down if needed! Rule: {rule}"  # pylint: disable=line-too-long
                )  # pylint: disable=line-too-long
            # ensure all conditions are legal
            if not "operation" in condition:
                raise ValueError(
                    f"Logical tag rule is missing operation! No default for ops! Rule: {rule}"
                )  # pylint: disable=line-too-long
            if condition["operation"] not in LogicalOperator.OPERATIONS:
                raise ValueError(
                    f"Logical tag rule has unsupported operation! Rule: {rule}"
                )
            if not "value" in condition:
                raise ValueError(f"Logical tag rule is missing value! Rule: {rule}")
            extra_keys = set(condition.keys()) - allowed_keys
            if extra_keys:
                logging.warning(
                    "Condition contains invalid keys: %s. Allowed keys are: %s. Rule: %s",
                    extra_keys,
                    allowed_keys,
                    rule,
                )
        # ensure root object is a supported object
        if root_object.lower() not in ["project", "dataset", "image"]:
            raise ValueError(
                f"Logical tag rule has unsupported root object! Can only tag Projects, Datasets, or Images! Rule: {rule}"  # pylint: disable=line-too-long
            )  # pylint: disable=line-too-long

    def compile_logical_rule(self, tag_rule: dict, path: dict):
        """
        Adds a given rule to the path.

        Args:
            tag_rule (dict): The logical rule to compile. It should be a dictionary
                         containing the necessary keys and values that define the rule.
            path (dict): The current path being compiled. It should be a dictionary
                         containing the necessary keys and values that define the path.

        Returns:
            dict: The compiled logical rule dictionary.
        """
        project_step = path
        dataset_step = project_step["children"][0]
        image_step = dataset_step["children"][0]

        root_object = tag_rule["rules"][0]["attribute_path"][0]

        conditions = []
        for conditional in tag_rule["rules"]:
            step = image_step
            obj = self._image
            if root_object.lower() == "project":
                step = project_step
                obj = self._project
            elif root_object.lower() == "dataset":
                step = dataset_step
                obj = self._dataset

            path = []
            for attribute in conditional["attribute_path"][1:]:
                getter = self.getter.get_getter(obj, attribute)
                path.append(getter)
                try:
                    obj = self._get_next_object(obj, getter, attribute)
                except ValueError as e:
                    # if errors on last step, we can allow it
                    if attribute == conditional["attribute_path"][-1]:
                        logging.warning(
                            "Last attribute in logical rule not found but that's allowed. Rule: %s",
                            tag_rule,
                        )
                        break
                    raise e
            conditions.append(
                {
                    "path": path,
                    "value": conditional["value"],
                    "operation": conditional["operation"],
                    "invert": conditional.get("invert", False),
                }
            )

        remove = tag_rule.get("type", "additive") == "subtractive"
        if remove and not self.conn.getObjects(
            "TagAnnotation", attributes={"textValue": tag_rule["name"]}
        ):
            raise ValueError(
                f"Tag {tag_rule['name']} does not exist, cannot remove it!"
            )

        step["rules"].append(
            {
                "conditions": conditions,
                "name": tag_rule["name"],
                "remove": remove,
                "absolute": tag_rule.get("absolute", True),
            }
        )

    def compile(self, ids: list[tuple[str, int]] = None):
        """Compile tagging rules into a format suitable for processing.

        This method transforms the tagging rules into a structured format that can be applied
        to OMERO objects. It handles both capture rules and logical rules, and can target
        specific objects if IDs are provided.

        Parameters
        ----------
        ids : list[tuple[str, int]], optional
            List of tuples containing object type and ID pairs to apply rules to.
            Each tuple should contain ('object_type', object_id).
            Supported object types are 'project', 'dataset', and 'image'.
            If None, rules will be applied to all projects.

        Returns
        -------
        list[dict]
            List of compiled rule dictionaries. Each dictionary contains:
            - project/dataset/image: int (object ID)
            - path: dict (hierarchical path structure)
            - regex: list (compiled regex patterns)

        Raises
        ------
        ValueError
            If an unsupported object type is provided or
            if strict mode is enabled and a specified object doesn't exist.

        Notes
        -----
        The method performs the following steps:
        1. Compiles the initial path structure
        2. Processes capture and logical rules
        3. Creates compiled rule sets for specified objects or all projects
        4. Validates object existence (if strict mode is enabled)
        """
        tagging_rules = self.tagging_rules
        compiled = {"path": self._format_initial_path(), "regex": []}
        for rule in tagging_rules:
            self._ensure_rule_type_exclusivity(rule)
            if rule.get("capture"):
                self._validate_capture_rule(rule)
                compiled["regex"].append(self.compile_capture_rule(rule))
            if rule.get("rules"):
                self._validate_logical_rule(rule)
                self.compile_logical_rule(  # updates path in place
                    rule, compiled["path"]
                )

        # schema 0/1 defaults to applying rules to all projects
        compiled_set = []
        if not ids:
            for project in self.conn.getObjects("Project"):
                item = copy.deepcopy(compiled)
                item.update({"project": project.getId()})
                compiled_set.append(item)
            return compiled_set

        # if ids are provided we only apply the rules to the specified objects
        # should be string int pairs, e.g. [("project", 1), ("dataset", 2), ("image", 3)]
        for obj_type, obj_id in ids:
            obj_type = obj_type.lower()
            if obj_type not in ["project", "dataset", "image"]:
                raise ValueError(f"Unsupported object type {obj_type}!")
            if self.conn.getObject(obj_type, obj_id) is None:
                if self.strict:
                    raise ValueError(f"Object {obj_type} {obj_id} does not exist!")
                logging.warning("Object %s %s does not exist!", obj_type, obj_id)
            compiled_path = copy.deepcopy(compiled["path"])
            if obj_type != "project":
                compiled_path = compiled_path["children"][0]
                if obj_type != "dataset":
                    compiled_path = compiled_path["children"][0]
            item = {
                obj_type: obj_id,
                "path": compiled_path,
                "regex": copy.deepcopy(compiled["regex"]),
            }
            compiled_set.append(item)
        return compiled_set

    def validate(self):
        """
        Runs the compilation process but gathers errors instead of returning the compiled rules.
        """
        errors = {}
        path = self._format_initial_path()
        tagging_rules = self.tagging_rules
        for i, rule in enumerate(tagging_rules):
            rule_errors = []
            try:
                self._ensure_rule_type_exclusivity(rule)
            except Exception as e:  # pylint: disable=broad-exception-caught
                rule_errors.append(e)
            try:
                if rule.get("capture"):
                    self._validate_capture_rule(rule)
                    self.compile_capture_rule(rule)
            except Exception as e:  # pylint: disable=broad-exception-caught
                rule_errors.append(e)
            try:
                if rule.get("rules"):
                    self._validate_logical_rule(rule)
                    self.compile_logical_rule(rule, path)
            except Exception as e:  # pylint: disable=broad-exception-caught
                rule_errors.append(e)
            if rule_errors:
                errors.update({f"rule_{i}": rule_errors})
        return errors


# Schema 1 is just schema 0 with a version field
class Schema1Compiler(Schema0Compiler):
    """Compiles the original yaml design into the dict defined in designs/compiled_rules.jsonc"""

    def __init__(self, conn, tagging_rules: dict):
        rules = tagging_rules.get("tag_rules")
        super().__init__(conn, rules)


def get_compiler(rule_path: str, conn: BlitzGateway) -> Schema0Compiler:
    """Returns the appropriate compiler based on the version field in the rules file."""
    rules = None
    if rule_path.endswith(".yml") or rule_path.endswith(".yaml"):
        with open(rule_path, "r", encoding="utf-8") as file:
            rules = yaml.safe_load(file)
    elif rule_path.endswith(".json") or rule_path.endswith(".jsonc"):
        with open(rule_path, "r", encoding="utf-8") as file:
            rules = json.load(file)
    else:
        raise ValueError("Unsupported file type for rules!")

    if "version" not in rules:
        return Schema0Compiler(conn, rules)
    if rules["version"] == 1:
        return Schema1Compiler(conn, rules)
    raise ValueError(f"Unsupported version {rules['version']}!")
