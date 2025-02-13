# Getting Started

This guide will help you get up and running with OMERO.RuleTagger

## Installation

Install OMERO.RuleTagger using pip:

```bash
pip install omero-ruletagger
```

## Basic Usage

### 1. Create a Rules File

Create a YAML file (e.g., `rules.yml`) defining your tagging rules:

```yaml
- name: "HasROIs"
    rules:
        - attribute_path: ["image", "roi", "count"]
            operation: gt
            value: 0

- name: "HighResolution"
    rules:
        - attribute_path: ["image", "primarypixel", "physicalsizex"]
            operation: lt
            value: 0.5
        - attribute_path: ["image", "primarypixel", "physicalsizex", "unit", "name"]
            operation: eq
            value: "MICROMETER"
```


### 2. Validate Your Rules

Before applying rules, validate them:

```bash
omero-ruletagger validate rules.yml
```

### 3. Test with Dry Run

To test rules without applying tags:

```bash
omero-ruletagger dry-run rules.yml -O "Dataset:456" -o results.csv -s localhost -u username -w password
```
Check the csv to confirm tags are being applied as expected.

### 4. Run the Tagger

Apply tags to OMERO objects:

```bash
omero-ruletagger run rules.yml -O "Image:123" -s localhost -u username -w password
```

## Connection Options
Tries to copy the OMERO cli connection options

* `-s, --server`: OMERO server hostname
* `-p, --port`: Server port
* `-u, --user`: Username
* `-w, --password`: Password
* `-k, --key`: Session key
* `-S, --secure`: Use secure connection


See the [Rules Documentation](rules.md) to build your own rules.yml file!