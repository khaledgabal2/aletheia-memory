"""Generate and exercise the Memory-owned review client against real HTTP."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from openapi_spec_validator import validate
from aletheia.service.review_contracts import review_document
from scripts.v1_4_phase0 import ROOT, NAMESPACE, local_service, request


def seed(memory, text):
    batch = memory.ingest(NAMESPACE, source_type="manual", content=text)
    run = memory.extract_candidates(NAMESPACE, batch_id=batch.id)
    return memory.list_candidates(NAMESPACE, extraction_run_id=run.id)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--typescript", action="store_true")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    if not args.output and not args.typescript and not args.browser:
        parser.error("choose --output, --typescript or --browser")
    with tempfile.TemporaryDirectory(prefix="aletheia-review-") as directory:
        with local_service(directory) as (service, url, tokens):
            first = seed(service.memory, "User prefers careful architecture notes.")
            second = seed(service.memory, "User prefers compact review summaries.")
            document = review_document(request(url, "GET", "/v1/openapi.json")["body"]["data"])
            validate(document)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
                print("Validated generated review projection from the running service.", flush=True)
            if args.typescript:
                env = {**os.environ, "ALETHEIA_TEST_URL": url, "ALETHEIA_TEST_TOKEN": tokens["reviewer"],
                       "ALETHEIA_TEST_FIRST": first.id, "ALETHEIA_TEST_SECOND": second.id}
                subprocess.run(["node", "dist/review.js"], cwd=ROOT / "contracts/typescript", env=env, check=True, timeout=45)
            if args.browser:
                from scripts.v1_4_read_contract import browser_server
                claim = service.memory.remember(namespace=NAMESPACE, memory_type="preference", subject="demo", predicate="prefers", object="reviewed architecture")
                proxy = browser_server(service, url, claim, review_candidates=(first, second))
                print(f"Disposable review browser fixture: http://127.0.0.1:{proxy.server_port}/", flush=True)
                try:
                    proxy.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    proxy.server_close()


if __name__ == "__main__":
    main()
