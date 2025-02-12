# OMERO.RuleTagger

## Description
OMERO.RuleTagger Python package for automated tagging of OMERO objects based on customizable rules and regex.

It works by walking the omero model as described by the omero-py wrappers and the underlying ObjectI classes. After the walk it compares a given reference value against the value it walked to, then tags if the condition passes.


## Quick Links
- [Getting Started](getting_started.md): Template for getting up and running.
- [Rule File](rules.md): In depth explanation of the rules.yml file.
- [Scheduling](scheduling.md): Describes some common patterns for running regularly.
- [Limitations](limitations.md): Describes some known limitations of this tool.