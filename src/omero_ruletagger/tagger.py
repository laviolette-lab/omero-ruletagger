"""
A module for automatically tagging OMERO objects based on rules.

This module provides functionality to apply tags to OMERO objects (Projects, Datasets, Images)
based on predefined rules. It supports both logical rules and regex-based rules, allowing for
flexible and automated tagging of OMERO objects based on their properties and names.

The module includes the OmeroRuleTagger class which handles the connection to OMERO and
implements the tagging logic. It supports dry runs for testing rule applications without
making actual changes to the OMERO database.

Classes
OmeroRuleTagger
    Main class that handles the application of tagging rules to OMERO objects.

The implementation prioritizes readability and simplicity over performance.
"""

import re
import logging
from typing import Optional

from omero.gateway import BlitzGateway, TagAnnotationWrapper, BlitzObjectWrapper

from .logic import LogicalOperator


class OmeroRuleTagger:  # pylint: disable=too-many-instance-attributes
    """
    Tags OMERO images based on a set of compiled rules.

    Notes
    -----
    It's not terribly fast, as it walks the objects one at a time.
    Performance could be improved by gathering objects all at once and
    organizing them into the heirarchy, but went with the simpler approach
    for ease of implementation and readability.
    May reimplement later if performance becomes a real issue.
    """

    DESCRIPTION = "Autotagged"

    def __init__(self, conn: BlitzGateway, dry_run: bool = False):
        self.conn = conn
        self.dry_run = dry_run

        self._logic = LogicalOperator()

        self.tag_map = self._gather_tag_map()
        self._rule_cache = {}
        self.true_tags = []
        self.false_tags = []
        self.dry_run_output = [("obj", "true", "false")]

    def apply_rules(self, rules: dict):
        """
        Main entry point for applying rules to objects.

        Parameters
        ----------
        rules : dict
            Compiled ruleset from a schema compiler.

        Raises
        ------
        ValueError
            The compiled ruleset requested to tag an unsupported object type.
        """
        for object_definition in rules:
            self.conn.SERVICE_OPTS.setOmeroGroup(-1)

            object_id = None
            object_type = None
            if "project" in object_definition:
                object_id = object_definition["project"]
                object_type = "Project"
            elif "dataset" in object_definition:
                object_id = object_definition["dataset"]
                object_type = "Dataset"
            elif "image" in object_definition:
                object_id = object_definition["image"]
                object_type = "Image"
            else:
                raise ValueError(
                    f"Invalid object definition: {object_definition} \nThis shouldn't get raised."
                )

            obj = self.conn.getObject(object_type, object_id)
            self.match_group(obj)

            path_def = object_definition["path"]
            regex_rules = object_definition["regex"]
            self._process_object_with_rules(obj, path_def, regex_rules)

    def _process_object_with_rules(
        self, obj: BlitzObjectWrapper, path_def: dict, regex_rules: dict
    ):
        """
        Process a single object against all its rules and recursively handle children.
        """
        self.true_tags = []
        self.false_tags = []
        self._apply_logical_rules(obj, path_def["rules"])
        self._apply_regex_rules(obj, regex_rules)
        if self.dry_run:
            logging.info(
                "%s:%s  TRUE: %s  FALSE: %s",
                obj.OMERO_CLASS,
                obj.getId(),
                self.true_tags,
                self.false_tags,
            )
            self.dry_run_output.append(
                (
                    f"{obj.OMERO_CLASS}:{obj.getId()}",
                    f"{self.true_tags}",
                    f"{self.false_tags}",
                )
            )
        for child_def in path_def["children"]:
            child_getter = child_def["getter"]
            for child in child_getter(obj):
                self._process_object_with_rules(child, child_def, regex_rules)

    def _apply_regex_rules(self, obj: BlitzObjectWrapper, rules: dict):
        """
        Apply all regex rules to a single object at once.
        """
        for rule in rules:
            if obj.OMERO_CLASS.lower() not in rule["objects"]:
                continue

            name = obj.getName()
            if not rule["include_extension"]:
                name = name.split(".")[0]

            tags = re.findall(rule["capture"], name)
            if rule["format"]:
                tags = [rule["format"].format(*tags)]

            for tag_name in tags:
                if str(tag_name) in [str(x) for x in rule["blacklist"]]:
                    continue
                tag = self._get_tag(obj.getDetails().group.id, tag_name, False)
                if self.dry_run:
                    self.true_tags.append(tag_name)
                else:
                    self._apply_tag(obj, tag)

    def _apply_logical_rules(self, obj, rules):
        """
        Apply all rules to a single object at once.
        """
        gid = obj.getDetails().group.id

        # gather objects to check rules against
        path_results = self._evaluate_all_paths(obj, rules)

        # Second pass - check rules using cached results
        for rule in rules:
            tag_name = rule["name"]
            remove = rule["remove"]
            absolute = rule["absolute"]

            # Check if any condition chain is satisfied using cached results
            applies = self._check_conditions(rule["conditions"], path_results)

            # Get or create tag
            tag = self._get_tag(gid, tag_name, remove)

            # Apply tag or track for dry run
            if self.dry_run:
                applies, remove = self._reconcile_opts(applies, remove, absolute)
                if remove:
                    self.false_tags.append(tag_name)
                elif applies:
                    self.true_tags.append(tag_name)
            else:
                if remove:
                    remove = tag_name
                self._apply_tag(obj, tag, applies, remove, absolute)

    def _check_conditions(self, conditions, path_results):
        """
        Check conditions against the gathered path_results.
        """

        def check_condition_chain(index=0):
            if index == len(conditions):
                return True

            condition = conditions[index]
            path_key = tuple(condition["path"])
            operation = condition["operation"]
            value = condition["value"]
            invert = condition["invert"]

            for result in path_results[path_key]:
                if self._logic.apply(operation, result, value, invert):
                    if check_condition_chain(index + 1):
                        return True
            return False

        return check_condition_chain()

    def _evaluate_all_paths(self, obj, rules):
        """
        Evaluate all unique condition paths for the given rules and cache results.
        """
        path_results = {}
        for rule in rules:
            for condition in rule["conditions"]:
                path_key = tuple(condition["path"])
                if path_key not in path_results:
                    results = list(self._evaluate_path(obj, condition["path"]))
                    path_results[path_key] = results
        return path_results

    def _evaluate_path(self, obj, path):
        """
        Evaluate a single path once and return all results.
        """
        if not path:
            yield obj
            return

        head = path[0]
        tail = path[1:]

        # If next operation is count, get length of results
        if len(tail) > 0 and tail[0] == "count":
            results = head(obj)
            if not isinstance(results, (list, tuple)):
                results = [results]
            yield len(results)
            return

        # if integer, index into list
        if isinstance(head, int):
            yield from self._evaluate_path(list(obj)[head], tail)
            return

        # Handle normal getter chain
        if head == "count":
            raise ValueError("Count must follow a getter in the path")

        if "pixels" in head.__name__.lower():
            obj._loadPixels()  # pixels seem to unload for some reason  # pylint: disable=protected-access

        results = head(obj)
        if not isinstance(results, (list, tuple)):
            results = [results]

        for item in results:
            yield from self._evaluate_path(item, tail)

    def _gather_tag_map(self) -> dict:
        """
        Gathers all tags created by this script from the server and organizes them by group.

        Returns
        -------
        dict
            dictionary of tags organized by group.
        """
        conn = self.conn
        tag_map = {}
        for g in conn.getGroupsMemberOf():
            gid = self._logic.ensure_unwrapped(g.id)
            group_tag_map = {}
            tags = conn.getObjects(
                "TagAnnotation",
                opts={"group": gid},
                attributes={"description": self.DESCRIPTION},
            )

            for tag in tags:
                group_tag_map.update({tag.getTextValue(): tag})
            tag_map.update({gid: group_tag_map})
        return tag_map

    def _get_tag(
        self, gid: int, tag_name: str, remove: bool = False
    ) -> Optional[TagAnnotationWrapper]:
        """
        Aquires a tag from the server or creates it if it doesn't exist.
        Except in the case of remove, where it returns None if the tag doesn't exist.

        Parameters
        ----------
        gid : int
            ID of the group to get the tag from.
        tag_name : str
            Name of tag to get.
        remove : bool
            Whether or not we intend on removing this tag.
            Important for removing tags not created by autotagging.

        Returns
        -------
        omero.gateway.TagAnnotationWrapper
            desired tag.
        """
        gid = self._logic.ensure_unwrapped(gid)
        group_tag_map = self.tag_map.get(gid, {})
        if tag_name in group_tag_map:
            return group_tag_map[tag_name]
        # you can remove tags that aren't from autotagging
        # so if remove and tag doesn't exist, return None,
        # handled later in _apply_tag
        if remove:
            return None
        tag = self._create_tag(tag_name)
        group_tag_map.update({tag_name: tag})
        return tag

    def _create_tag(self, tag_name: str) -> TagAnnotationWrapper:
        """
        Creates a tag on the server.
        Does not upload if doing a dry run.

        Parameters
        ----------
        tag_name : str
            Name of the string to create.

        Returns
        -------
        omero.gateway.TagAnnotationWrapper
            Created tag
        """
        logging.info("Creating tag %s", tag_name)
        tag = TagAnnotationWrapper(self.conn)
        tag.setDescription(self.DESCRIPTION)
        tag.setValue(tag_name)
        if not self.dry_run:
            tag.save()
        return tag

    def match_group(self, obj: BlitzObjectWrapper):
        """
        Matches the group of the session to the group of the object.

        Parameters
        ----------
        obj : BlitzObjectWrapper
            Any given object in OMERO.
        """
        group_id = obj.getDetails().group.id
        group_id = self._logic.ensure_unwrapped(group_id)
        self.conn.SERVICE_OPTS.setOmeroGroup(group_id)

    def _reconcile_opts(self, apply, remove, absolute):
        if absolute and not apply:
            remove = True
            apply = True
        return apply, remove

    # executive decision: more readable to have this all together
    def _apply_tag(  # pylint: disable=too-many-arguments, too-many-branches
        self, obj, tag, apply=True, remove=False, absolute=False
    ):
        apply, remove = self._reconcile_opts(apply, remove, absolute)

        # if rule does not apply, ignore
        if not apply:
            return

        if remove:
            link_id, tag_name = None, None
            # if tag is not from autotagger, find the tag and link id
            if tag is None:
                tags = self.conn.getObjects(
                    "TagAnnotation", attributes={"textValue": remove}
                )
                for t in tags:
                    for annot in obj.listAnnotations():
                        if annot.id == t.id:
                            link_id = annot.link.id
                if link_id is None:
                    return
                tag_name = remove
            # should not be none if from autotagger
            else:
                for annot in obj.listAnnotations():
                    if annot.id == tag.id:
                        link_id = annot.link.id
                        tag_name = tag.getTextValue()
                        break
            # link id is none when image already is not tagged with this tag
            if link_id is not None:
                self.conn.deleteObjects("ImageAnnotationLink", [link_id])
                logging.info("Removed tag %s from %s", tag_name, obj)
        # else link the tag
        else:
            if tag.getId() in [x.id for x in obj.listAnnotations()]:
                return
            obj.linkAnnotation(tag)
            logging.info("Tagged %s with %s", obj, tag.getTextValue())
