"""Generate or exercise current discovery contracts using a real local service."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from openapi_spec_validator import validate

from aletheia.service.contracts import discovery_document
from scripts.v1_4_phase0 import ROOT, local_service, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--typescript", action="store_true")
    args = parser.parse_args()
    if not args.output and not args.typescript:
        parser.error("choose --output or --typescript")
    with tempfile.TemporaryDirectory(prefix="aletheia-discovery-") as directory:
        with local_service(directory) as (_, base_url, tokens):
            response = request(base_url, "GET", "/v1/openapi.json")
            assert response["status"] == 200
            schema = discovery_document(response["body"]["data"])
            validate(schema)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
                print(f"Validated six discovery operations from the running service: {args.output}")
            if args.typescript:
                env = {**os.environ, "ALETHEIA_TEST_URL": base_url, "ALETHEIA_TEST_TOKEN": tokens["agent"]}
                subprocess.run(["node", "dist/discovery.js"], cwd=ROOT / "contracts/typescript", env=env, check=True, timeout=30)


if __name__ == "__main__":
    main()
