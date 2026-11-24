"""Check the storyboard contract before running a generation stage."""

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "storyboard.schema.json"


def read_json(path):
    def reject_constant(token):
        raise ValueError(f"invalid JSON number {token}")

    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, ValueError) as error:
        raise ValueError(f"{path}: {error}") from error


def validate_storyboard(path):
    schema = read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    storyboard = read_json(path)
    errors = [
        f"{error.json_path}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(storyboard)
    ]
    if errors:
        raise ValueError(f"{path}:\n" + "\n".join(errors))

    shot_positions = {}
    for index, shot in enumerate(storyboard["shots"]):
        shot_id = shot["id"]
        if shot_id in shot_positions:
            first = shot_positions[shot_id]
            raise ValueError(
                f"{path}: $.shots[{index}].id duplicates shot {shot_id} "
                f"at $.shots[{first}].id"
            )
        shot_positions[shot_id] = index
    return storyboard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("storyboard", nargs="?", type=Path, default=ROOT / "storyboard.json")
    args = parser.parse_args()
    try:
        storyboard = validate_storyboard(args.storyboard)
    except (ValueError, SchemaError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Valid storyboard ({len(storyboard['shots'])} shots)")


if __name__ == "__main__":
    main()
