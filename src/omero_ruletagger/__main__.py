"""OMERO Rule Tagger Command Line Interface.

This module provides a command-line interface for applying tags to OMERO objects
based on rules defined in a configuration file. It supports validation of rules,
actual tagging of objects, and dry-run simulation of tagging operations.

The module connects to an OMERO server using either username/password authentication
or by joining an existing session using a session key. It can process multiple OMERO
objects (Images, Datasets, or Projects) in a single run.

Features:
    - Validate rules without applying them
    - Apply tags to OMERO objects based on rules
    - Perform dry-run simulations of tag applications
    - Support for secure connections
    - Verbose logging option
    - CSV output for dry-run results
"""

import argparse
import logging
import csv
import sys

from omero import client, ClientError
from omero.gateway import BlitzGateway

from .tagger import OmeroRuleTagger
from .compiler import get_compiler


def write_output(output: list[list[str]], output_path: str) -> None:
    """Write CSV output to a file.

    Parameters
    ----------
    output : list[list[str]]
        List of rows, where each row is a list of strings to be written as CSV
    output_path : str
        Path to the output CSV file

    Returns
    -------
    None
    """
    with open(output_path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        for line in output:
            writer.writerow(line)


def create_gateway(conn_params: dict) -> BlitzGateway:
    """Create and return a BlitzGateway connection to OMERO.

    Parameters
    ----------
    conn_params : dict
        Dictionary containing connection parameters:
        - key : str, optional
            Session key for joining existing session
        - host : str
            OMERO server hostname
        - port : int
            OMERO server port
        - username : str
            Username for authentication (required if not using session key)
        - passwd : str
            Password for authentication (required if not using session key)
        - try_super : bool, optional
            Whether to try to connect as administrator
        - secure : bool, optional
            Whether to use secure connection

    Returns
    -------
    BlitzGateway
        Connected OMERO gateway object

    Raises
    ------
    ValueError
        If required connection parameters are missing or connection fails
    """
    if conn_params["key"]:
        ome_client = client(conn_params["host"], conn_params["port"])
        ome_client.joinSession(conn_params["key"])
        conn_params = {"client_obj": ome_client}
    else:
        conn_params.pop("key")
        if conn_params["username"] is None:
            raise ValueError("Username is required if not joining a session")
        if conn_params["passwd"] is None:
            raise ValueError("Password is required if not joining a session")
    conn = None
    try:
        conn = BlitzGateway(**conn_params)
    except ClientError as e:
        try:
            conn.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        raise ValueError(
            f"Failed to connect to OMERO, likely missing information: {e}"
        ) from e

    conn.connect()
    if not conn.isConnected():
        try:
            conn.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        raise ValueError("Failed to connect to OMERO")

    logging.info("Connected to OMERO as %s", conn.getUser().getName())
    return conn


def parse_omero_object(conn: BlitzGateway, obj_str: str) -> tuple[str, str]:
    """Parse OMERO object string into type and ID.

    Parameters
    ----------
    conn : BlitzGateway
        Connected OMERO gateway object
    obj_str : str
        String in format "Type:ID" (e.g. "Image:123")

    Returns
    -------
    tuple[str, str]
        Tuple containing (object_type, object_id)

    Raises
    ------
    SystemExit
        If object string format is invalid, object type is invalid,
        or object does not exist in OMERO
    """
    obj_split = obj_str.split(":")
    if len(obj_split) != 2:
        logging.error("Invalid object format: %s", obj_str)
        sys.exit(1)
    obj_type, obj_id = obj_split
    if obj_type.lower() not in ("image", "dataset", "project"):
        logging.error("Invalid object type: %s", obj_type)
        sys.exit(1)
    if conn.getObject(obj_type, obj_id) is None:
        logging.error("Object not found: %s", obj_str)
        sys.exit(1)
    return (obj_type, obj_id)


def setup_parser() -> argparse.ArgumentParser:
    """Set up command line argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser with all command line options
    """
    parser = argparse.ArgumentParser(
        prog="OMERO.RuleTagger", description="OMERO.RuleTagger CLI"
    )
    parser.add_argument("-s", "--server", help="OMERO server hostname")
    parser.add_argument("-p", "--port", help="OMERO server port")
    parser.add_argument("-u", "--user", "--username", help="OMERO Username")
    parser.add_argument("-w", "--password", help="OMERO Password")
    parser.add_argument("-k", "--key", help="Key of an existing session")
    parser.add_argument(
        "-S",
        "--secure",
        action="store_true",
        help="Use secure connection for the entire process",
    )
    parser.add_argument(
        "--sudo",
        action="store_true",
        help="Create session as this admin",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    validate_parser = subparsers.add_parser("validate", help="Check rules")
    validate_parser.add_argument("rules", help="Path to rules file")

    run_parser = subparsers.add_parser("run", help="Apply tags")
    run_parser.add_argument("rules", help="Path to rules file")
    run_parser.add_argument("--object", "-O", help="Objects to tag", action="append")

    dry_run_parser = subparsers.add_parser("dry-run", help="Simulate tagging")
    dry_run_parser.add_argument("rules", help="Path to rules file")
    dry_run_parser.add_argument(
        "--object", "-O", help="Objects to tag", action="append"
    )
    dry_run_parser.add_argument("--output", "-o", help="Output csv file")
    return parser


def main():
    """Main entry point for the OMERO Rule Tagger command line application.

    This function handles command line argument parsing, logging setup, OMERO connection management,
    and execution of the specified command (validate, run, or dry-run).

    Notes
    -----
    The function performs the following main tasks:
        1. Parses command line arguments
        2. Sets up logging based on verbosity
        3. Establishes connection to OMERO server
        4. Executes the requested command
        5. Handles errors and cleanup

    Returns
    -------
    None
        The function exits with code 0 on success, 1 on error

    Raises
    ------
    Exception
        Any exceptions during execution are caught, logged, and result in exit code 1

    Parameters
    ----------
    None
        All parameters are obtained from command line arguments through argparse

    Examples
    --------
    $ python -m omero_ruletagger validate rules.yml
    $ python -m omero_ruletagger run rules.yml --object "Image:123"
    $ python -m omero_ruletagger dry-run rules.yml -O "Dataset:456" -o results.csv
    """
    parser = setup_parser()
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    conn_params = {
        "username": args.user,
        "passwd": args.password,
        "host": args.server,
        "port": args.port,
        "try_super": args.sudo,
        "secure": args.secure,
        "key": args.key,
    }
    conn = None
    exit_code = 0
    try:
        conn = create_gateway(conn_params)
        if not args.command:
            logging.error("No command specified")
            parser.print_help()
            exit_code = 1
        compiler = get_compiler(args.rules, conn)
        if args.command == "validate":
            results = compiler.validate()
            if results:
                for rule, errors in results.items():
                    for error in errors:
                        logging.error("%s: %s", rule, str(error))
                exit_code = 1
                print("Validation failed")
            else:
                print("Validation successful")
        elif args.command == "run":
            obj_ids = [parse_omero_object(conn, obj) for obj in args.object]
            rules = compiler.compile(obj_ids)
            tagger = OmeroRuleTagger(conn)
            tagger.apply_rules(rules)
            print("Tags applied")
        elif args.command == "dry-run":
            obj_ids = [parse_omero_object(conn, obj) for obj in args.object]
            rules = compiler.compile(obj_ids)
            tagger = OmeroRuleTagger(conn, dry_run=True)
            tagger.apply_rules(rules)
            output_path = args.output or "rules_tagged.csv"
            write_output(tagger.dry_run_output, output_path)
            print(f"Dry run output written to {output_path}")
        else:
            logging.error("Invalid command specified: %s", args.command)
            parser.print_help()

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error: %s", e)
        exit_code = 1

    finally:
        if conn:
            conn.close()
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
