"""An agent process receives candidate-write access, never review credentials."""
import argparse
import json
import os
from aletheia.client import AletheiaClient, AletheiaClientError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["capture", "read"])
    parser.add_argument("operation_key", nargs="?")
    args = parser.parse_args()
    token = os.environ.get("ALETHEIA_AGENT_TOKEN")
    url = os.environ.get("ALETHEIA_URL")
    namespace = os.environ.get("ALETHEIA_NAMESPACE", "user/demo")
    if not token or not url:
        raise SystemExit("Set ALETHEIA_URL and ALETHEIA_AGENT_TOKEN, or run operator_demo.py for a disposable local demo.")
    client = AletheiaClient(url, token, timeout=10)
    if not hasattr(client, "current_principal"):
        raise SystemExit("This starter needs the 1.4 development SDK, not the published 1.3.1 SDK.")
    try:
        principal = client.current_principal()
        if not {"memory-read-v1", "agent-onboarding-v1"} <= set(principal.get("supported_profiles", [])):
            raise SystemExit("The service needs memory-read-v1 and agent-onboarding-v1; no candidate was written.")
        capabilities = set(principal["capabilities"])
        needed = {"memory:read", "memory:context", "memory:write_candidate"}
        if not needed <= capabilities or capabilities & {"memory:admin", "memory:review", "memory:write_active"}:
            raise SystemExit("Use a restricted agent token with read/context/write_candidate and without admin, review or active-write access.")
        if args.action == "capture":
            if not args.operation_key:
                raise SystemExit("Capture requires an explicit operation key as its second argument.")
            result = client.remember_candidate(namespace=namespace, memory_type="preference",
                subject="user", predicate="prefers", object="careful architecture notes",
                evidence_text="User prefers careful architecture notes.", idempotency_key=args.operation_key, contract="agent-onboarding-v1")
            print(json.dumps({"candidate_id": result["candidate"]["id"]}))
        else:
            pack = client.context_pack(namespace=namespace, query="architecture", retrieval_mode="lexical", record_usage=False)
            print(pack["markdown"])
            print("Visible context items:", len(pack["items"]))
            if pack["items"]:
                explanation = client.explain_claim(pack["items"][0]["claim_id"])
                print("Provenance:", explanation["evidence"][0]["content"])
    except AletheiaClientError as error:
        raise SystemExit(f"Memory request failed ({error.status_code or 'transport'}). Check discovery, token permissions and namespace with doctor --read-only.") from None
    except (OSError, ValueError):
        raise SystemExit("Memory response unavailable or invalid. Do not blindly repeat a candidate write; ask the operator to inspect pending candidates.") from None


if __name__ == "__main__":
    main()
