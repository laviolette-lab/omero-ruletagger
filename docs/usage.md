## Usage

1. Define your tag rules in a YAML file. See the provided example file for the required structure and syntax.

2. Run the script from the command line using the following syntax:
### From Install: (pypi coming soon)
```
python3 -m omero_autotagger <path to tag_rules.yml> [path to patch.py] -s <server> -p <port> -u [user] -w [password] -S [secure] --session [session_key]
```
### From Source:
```
python3 src/omero_autotagger <path to tag_rules.yml> [path to patch.py] -s <server> -p <port> -u [user] -w [password] -S [secure] --session [session_key]
```

Here is a brief explanation of each argument:

- `tag_rules.yml`: Required. Path to the YAML file containing the tagging rules to be applied.
- `patch.py`: Path to the Python patch script to use for tagging.
- `server`: Required. Address of the OMERO server to connect to.
- `port`: Required. Port number of the OMERO server to connect to.
    * With the increased adoption of OMERO API over websockets, we decided to make this required, may be assumed in future updates.
- `user`: Username for the OMERO server. This is required if no session key is provided.
- `password`: Password for the OMERO server. This is required if no session key is provided.
- `secure`: Establishes a secure connection to the server. If not specified, a secure connection is used to login and then switched to unsecure by default.
- `session`: Session key to use for connecting to the server. If this is provided, username and password will be ignored.

## Example Usage

Given a YAML file `tag_rules.yaml` and patch script `patch.py`:

```
python3 -m omero_autotagger rules.yml patch.py -s myserver.com -p 4064 -u myuser -w mypassword
```

Or using a session key:

```
python3 -m omero_autotagger rules.yml patch.py -s myserver.com -p 4064 --session mysesskey
```

This will establish a connection to the specified OMERO server, load the tagging rules from the provided YAML file, apply these rules using the provided patch script (if any), and tag the images accordingly.
