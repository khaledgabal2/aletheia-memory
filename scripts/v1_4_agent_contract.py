"""Generate and execute the candidate-first onboarding contract."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from openapi_spec_validator import validate
from aletheia.service.onboarding_contract import onboarding_document
from scripts.v1_4_phase0 import ROOT, local_service, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--typescript", action="store_true")
    args = parser.parse_args()
    if not args.output and not args.typescript:
        parser.error("choose --output or --typescript")
    with tempfile.TemporaryDirectory(prefix="aletheia-agent-") as folder:
        with local_service(folder) as (_, url, tokens):
            document = onboarding_document(request(url, "GET", "/v1/openapi.json")["body"]["data"])
            validate(document)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
                print("Validated candidate-first onboarding projection from actual service.")
            if args.typescript:
                subprocess.run(["node", "dist/onboarding.js"], cwd=ROOT / "contracts/typescript",
                    env={**os.environ, "ALETHEIA_TEST_URL": url, "ALETHEIA_TEST_TOKEN": tokens["agent"],
                        "ALETHEIA_TEST_REVIEWER": tokens["reviewer"]}, check=True, timeout=45)


if __name__ == "__main__":
    main()
