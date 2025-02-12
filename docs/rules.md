# Rules Documentation

These YAML configurations define custom logic for tagging OMERO objects.
There are two kinds of tag rules, regex rules and logical rules. 
Regex rules uses regex capture groups along with an optional format string that is compared to the name. 
Logical rules compare object properties (like ROI counts, stroke colors, or descriptions) to specified values to evaluate tagging conditions. For example, you could add a tag that defines whether or not an image has ROIs by checking that the amount of ROIs is greater than 0.

## Regex Rules:
```yaml
- capture: "([^_.]+)"
  format: "{}"
  include_extension: False
  blacklist:
    - 1
```
### Regex rules have three configuration options
* __Capture__
    * The capture option is required. This defines the capture regex to split up the text.
* __Format__
    * The format is optional. It is required to have the same number of replacement fields as capture groups. If absent it defaults to "{}" * num_capture_groups using underscores to divide each group.
* __Extension Inclusion__
    * The extension is not included by default. It does this by taking all the characters before the first period.
* __Blacklist__
    * The blacklist is optional. It blocks certain values captured values from being tagged. It defaults to blacklisting nothing.

### In the above example, an image named "SUBJ_SAMPLE_1.ome.tiff" would be tagged as follows:
 * __SUBJ__
 * __SAMPLE__

It is split by underscores as defined in the capture regex. The file extension is not included in the capture process, and the "1" is captured, but then ignored from the blacklist.

## Logical Rules
```yaml
- name: "PhysicalSizeTest"
  absolute: True
  type: additive
  rules:
    - attribute_path: ["image", "primarypixel", "physicalsizex"]
      operation: eq
      value: 1000
      invert: False
    - attribute_path: ["image", "primarypixel", "physicalsizey"]
      operation: eq
      value: 1000
    - attribute_path: ["image", "primarypixel", "physicalsizex", "unit", "name"]
      operation: eq
      value: "MICROMETER"
```

### Logical rules have a number of configuration options

* __Name__
    * The name option is required and defines the what the tag will be called.
* __Absolute__
    * Tags are absolute by default. This means that if the conditions evaluate to False, then the object will be untagged if it is already tagged.
* __Type__
    * Tags can be additive or subtractive, with additive as the default.
    * Additive tags mean that you should tag the object if the conditions evaluate to True. 
    * Subtractive tags remove tags when the conditions evaluate to True.
        * Subtractive tags cannot be absolute. Meaning tags will not be added to an object if a subtractive rule evaluates to False.
        * Subtractive rules can remove tags that do not originate from RuleTagger.
* __Rules__ (poor name from original schema, likely to be changed to 'conditions' or 'logic' in the next schema)
    * Rules are required. They define the conditions to evaluate to know whether to tag an object with the tag (or remove if subtractive). 
    * Each condition in the list is AND logic.
        * OR logic could be done by defining two set of rules for the same tag name.
    * __Attribute Path__
        * Defines the path to walk on the OMERO object path.
        * Each Attribute Path must start on the same parent object as this defines the kind of object to tag, currently tagging is only supported for __Images__, __Datasets__, and __Projects__.
        *  The getters for each property are gathered from omero-py/zeroc-ice at compile time.
        * You can use the omero-py and omero model documentation to find the path to walk.
        * There is currently only one functioning keyword
            * __count__: counts the number of children from the last getter
    * __Operation__
        * Operation is required. Defines the comparison to perform.
        * Supported operations are as follows
            - gt: Greater than
            - lt: Lesser than
            - eq: Equal to
            - ge: Greater or Equal
            - le: Lesser or Equal
            - ne: Not Equal to
            - match: Compares value to (non-capture) regex
            - always: Always True
            - never: Never True
    * __Value__
        * Required. Static value that is compared to the value we found from our walk.
    * __Invert__
        * Defaults to False. If True, it inverts the logic of the Operation.

## Schemas
OMERO.RuleTagger currently has two nearly identical schemas.
* v0
    * v0 is the schema from the original implementation, with some goodies added during the refactor.
* v1
    * v1 is the exact same, except for a version field, placing the entirety of schema v0 in the '__tag_rules__' field.

```yaml
# Schema v0
- capture: "([^_.]+)"
  format: "{}"
  include_extension: False
  blacklist:
    - 1
---
# Schema v1
version: v1
tag_rules:
    - capture: "([^_.]+)"
      format: "{}"
      include_extension: False
      blacklist:
        - 1
```

* Schema v1 was introduced to prepare for the changeover to schema v2.
    * Schema v2 is currently being sketched out in the design directory.
    * Schema v2 will seek to address many of the already known limitations plus limitations that come up in user feedback.