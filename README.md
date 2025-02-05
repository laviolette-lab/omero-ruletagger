[![PyPI version](https://badge.fury.io/py/omero-ruletagger.svg)](https://badge.fury.io/py/omero-ruletagger)  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)  [![Python Versions](https://img.shields.io/pypi/pyversions/omero-ruletagger.svg)](https://pypi.org/project/omero-ruletagger/)
# OMERO.RuleTagger (Previously Known as [OMERO.Autotagger](https://github.com/LavLabInfrastructure/omero-autotagger))

A Python package for automated tagging of OMERO objects based on customizable rules and regex.

It works by walking the omero model as described by the omero-py wrappers and the underlying ObjectI classes. After the walk it compares a given reference value against the value it walked to, then tags if the condition passes.

## Known Limitations
* Currently impossible to add arguments to the model walk
  * For example a you can't filter a condition to only check annotations in a certain namespace
  * This example could be fixed by comparing the 'ns' property against the desired value, but it still won't filter 
* Cannot specify objects to operate on within the rules file.
  * Planned addition in schemav2 but wanted to get this out and get some feedback for schemav2
* Doesn't handle Annotations very well.
  * This is because the omero-py package doesn't have getters for specific annotation types
    * This causes AttributeErrors
  * Map and Table Annotations especially need extra thought to be able to meaningfully rule against
* Also doesn't handle properties
  * Due to the compilation process, we need getters to access properties
  * Could be possible to add with some lambda
    * Decided to leave as is for now because most properties have a getter (thanks java!)
* Pretty slow and inefficient
  * Makes more requests than it needs to
  * Causes it to take longer than it needs to
  * Decided to leave as is for readability sake
    * We run it once a night, could probably do it once a week
    * Both walking and recursion can get complex, tried my best to stay legible (unlike my first implementation)
    
## Documentation
For a proper in-depth explanation of the tool use the [documentation.](https://omero-ruletagger.readthedocs.io/en/stable)

## Installation

Install using pip:

```bash
pip install omero-ruletagger
```

### Dependencies

- Python ≥3.8  
- PyYAML  
- inflect  
- omero-py  

## Usage

### Command Line Interface

The package provides three main commands:

1. Validate rules:

```bash
omero-ruletagger validate rules.yml
```

2. Apply tags:

```bash
omero-ruletagger run rules.yml -O "Image:123" -O "Dataset:456"
```

3. Dry run:

```bash
omero-ruletagger dry-run rules.yml -O "Image:789" -o results.csv
```

### Connection Options

- `-s`, `--server`: OMERO server hostname  
- `-p`, `--port`: OMERO server port  
- `-u`, `--user`: OMERO username  
- `-w`, `--password`: OMERO password  
- `-k`, `--key`: Existing session key  
- `-S`, `--secure`: Use secure connection  
- `--sudo`: Connect as administrator  
- `-v`, `--verbose`: Enable verbose logging  

### Rule Configuration

Create a YAML file defining your tagging rules. Example:

```yaml
# test_rules.yml
- capture: "([^-.]+)"
  blacklist:
    - 1

- name: "FALSE"
  rules:
    - attribute_path: ["image", "roicount"]
      operation: lt
      value: 1

- name: "TRUE"
  rules:
    - attribute_path: ["image", "roi", "count"]
      operation: gt
      value: 0

- name: "Subtractive"
  absolute: false
  type: subtractive
  rules:
    - attribute_path: ["image", "roi","count"]
      operation: gt
      value: 0

- name: "UselessAND_TRUE"
  rules:
    - attribute_path: ["image", "roi", "shape", "strokecolor"]
      operation: eq
      value: 255
    - attribute_path: ["image", "roi", "shape", "count"]
      operation: eq
      value: 1

- name: "InherentlyFalseAND"
  rules:
    - attribute_path: ["image", "roi", "shape", "strokecolor"]
      operation: eq
      value: 255
    - attribute_path: ["image", "roi", "shape", "strokecolor"]
      operation: eq
      value: 254

- name: "DescriptionTest"
  rules:
    - attribute_path: ["image", "descriptions"]
      operation: match
      value: ".*test.*"

- name: "PhysicalSizeTest"
  rules:
    - attribute_path: ["image", "primarypixel", "physicalsizex"]
      operation: eq
      value: 1000
    - attribute_path: ["image", "primarypixel", "physicalsizey"]
      operation: eq
      value: 1000
    - attribute_path: ["image", "primarypixel", "physicalsizex", "unit", "name"]
      operation: eq
      value: "MICROMETER"
```


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [`LICENSE.txt`](LICENSE.txt) file for details.

## Links

- [Documentation](https://github.com/laviolette-lab/omero-ruletagger#readme)  
- [Source Code](https://github.com/laviolette-lab/omero-ruletagger)  
- [Issue Tracker](https://github.com/laviolette-lab/omero-ruletagger/issues)