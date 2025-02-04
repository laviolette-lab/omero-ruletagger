import argparse
import logging
import csv
import sys

from omero import client, ClientError
from omero.gateway import BlitzGateway

from .tagger import OmeroRuleTagger
from .compiler import get_compiler


def write_output(output, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        for line in output:
            writer.writerow(line)


def create_gateway(conn_params):
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
        except Exception:
            pass
        raise ValueError(
            f"Failed to connect to OMERO, likely missing information: {e}"
        ) from e

    conn.connect()
    if not conn.isConnected():
        try:
            conn.close()
        except Exception:
            pass
        raise ValueError("Failed to connect to OMERO")

    logging.info("Connected to OMERO as %s", conn.getUser().getName())
    return conn


def parse_omero_object(conn: BlitzGateway, obj_str: str):
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


def setup_parser():
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
    parser = setup_parser()
    args = parser.parse_args()

    # Set up logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level)

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

    except Exception as e:
        logging.error("Error: %s", e)
        exit_code = 1

    finally:
        if conn:
            conn.close()
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
