"""Explicit, synthetic local-model recipe checks; no model downloads or fallback."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import socket
import tempfile
import threading
import time
from urllib.request import Request

from aletheia import Memory
from aletheia.core.errors import ValidationError
from aletheia.provider_http import local_opener
from aletheia.semantic import provider_for_name
from aletheia.version import software_version

EMBEDDING_DIGEST = "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f"
LLM_DIGESTS = {
    "qwen3:0.6b": "7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435",
    "llama3.1:8b": "46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e",
}
NAMESPACE = "user/local-recipe"


def configure(base, embedding_model, llm_model):
    # The recipe is isolated from unrelated provider credentials/configuration.
    for name in list(os.environ):
        if name.startswith(("ALETHEIA_EMBEDDING_", "ALETHEIA_LLM_")):
            del os.environ[name]
    embedding = {"ENDPOINT":base+"/api/embed", "MODEL":embedding_model, "DIMENSION":"768",
        "DOCUMENT_PREFIX":"search_document: ", "QUERY_PREFIX":"search_query: ",
        "MODEL_REVISION":EMBEDDING_DIGEST, "LOCAL_ONLY":"true"}
    llm = {"ENDPOINT":base+"/api/chat", "MODEL":llm_model, "LOCAL_ONLY":"true", "STRUCTURED_OUTPUT":"true",
        "NUM_CTX":"4096", "KEEP_ALIVE":"0", "TIMEOUT":"60"}
    if llm_model.startswith("qwen3:"):
        llm["THINK"] = "false"
    os.environ.update({"ALETHEIA_EMBEDDING_OLLAMA_STYLE_"+key:value for key,value in embedding.items()})
    os.environ.update({"ALETHEIA_LLM_OLLAMA_STYLE_"+key:value for key,value in llm.items()})
    return {"embedding":embedding, "llm":llm}


def embedding_checks(memory, base):
    expected = []
    for subject,predicate,obj in [("user","prefers","bicycles for commuting"),("database","uses","encrypted backup archives")]:
        expected.append(memory.remember(namespace=NAMESPACE,memory_type="preference",subject=subject,
            predicate=predicate,object=obj,source_type="synthetic-recipe"))
    run = memory.index_semantic(NAMESPACE,provider="ollama_style")
    assert run.indexed_count == 2
    retrieval = []
    for query,claim in zip(["riding a bike to work","keeping backup files confidential"],expected):
        hits = memory.retrieve(NAMESPACE,query,mode="semantic",semantic_provider="ollama_style")
        assert hits and hits[0].claim_id == claim.id
        retrieval.append({"query":query,"top_result":hits[0].text,"semantic_score":hits[0].semantic_score})
    assert memory.verify_semantic_index(NAMESPACE,provider="ollama_style").verified_count == 2
    os.environ["ALETHEIA_EMBEDDING_OLLAMA_STYLE_DIMENSION"] = "767"
    try:
        provider_for_name("ollama_style").embed_texts(["Synthetic dimension check"])
    except ValueError as error:
        assert "dimension" in str(error)
    else:
        raise AssertionError("Unexpected provider dimensions were accepted")
    try:
        memory.retrieve(NAMESPACE,"bike",mode="semantic",semantic_provider="ollama_style")
    except ValidationError as error:
        assert "reindex" in str(error)
    else:
        raise AssertionError("Incompatible index was reused")
    os.environ["ALETHEIA_EMBEDDING_OLLAMA_STYLE_DIMENSION"] = "768"
    os.environ["ALETHEIA_EMBEDDING_OLLAMA_STYLE_MODEL_REVISION"] = EMBEDDING_DIGEST+":reindex-rehearsal"
    assert memory.index_semantic(NAMESPACE,provider="ollama_style").stale_count == 2
    os.environ["ALETHEIA_EMBEDDING_OLLAMA_STYLE_MODEL_REVISION"] = EMBEDDING_DIGEST
    assert memory.index_semantic(NAMESPACE,provider="ollama_style").indexed_count == 2
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",0))
        unused_port = probe.getsockname()[1]
        # Bound but not listening: guaranteed unavailable while this socket lives.
        os.environ["ALETHEIA_EMBEDDING_OLLAMA_STYLE_ENDPOINT"] = f"http://127.0.0.1:{unused_port}/api/embed"
        try:
            provider_for_name("ollama_style").embed_texts(["Synthetic unavailable-provider check"])
        except ValueError:
            pass
        else:
            raise AssertionError("Unavailable provider silently succeeded")
    os.environ["ALETHEIA_EMBEDDING_OLLAMA_STYLE_ENDPOINT"] = base+"/api/embed"
    assert memory.retrieve(NAMESPACE,"bicycles",mode="lexical")
    return {"status":"passed", "dimension":768,"retrieval":retrieval,
        "checks":["real vectors and paraphrased retrieval","stored provenance/index verification","wrong response dimension refused",
                  "changed preset/dimension refused before query","explicit reindex preserves compatibility","unavailable provider fails; lexical remains usable"]}


def llm_checks(memory):
    namespace = NAMESPACE + "/extraction"
    active_before = len(memory.list_claims(namespace=namespace))
    candidates, runs = [], []
    samples = [("User prefers careful architecture notes.","architecture"),
               ("User prefers tea instead of coffee.","tea"),
               ("User prefers concise weekly progress updates.","progress")]
    for text,term in samples:
        batch = memory.ingest(namespace,source_type="synthetic-recipe",content=text)
        started = time.perf_counter()
        run = memory.extract_candidates(namespace,batch_id=batch.id,extractor="ollama_style")
        items = memory.list_candidates(namespace,extraction_run_id=run.id)
        meaningful = bool(items) and all(item.candidate_status == "pending_review" for item in items) and any(term in item.object.lower() for item in items)
        runs.append({"source":text,"candidate_count":len(items),"seconds":round(time.perf_counter()-started,3),
            "status":"passed" if meaningful else "failed", "warnings":run.warnings, "candidate_states":[item.candidate_status for item in items]})
        for item in items:
            assert item.candidate_status in {"pending_review", "invalid", "needs_conflict_resolution", "duplicate"} and item.metadata["llm_output"] is True, "LLM output escaped candidate governance"
            assert item.evidence_spans[0].evidence_id in batch.evidence_ids, "Candidate evidence escaped its synthetic batch"
            candidates.append(asdict(item))
    assert len(memory.list_claims(namespace=namespace)) == active_before, "Extraction created an active claim"
    # Missing models fail; the recipe never pulls one or calls a hosted fallback.
    selected = os.environ["ALETHEIA_LLM_OLLAMA_STYLE_MODEL"]
    os.environ["ALETHEIA_LLM_OLLAMA_STYLE_MODEL"] = "aletheia-deliberately-missing-recipe-model"
    batch = memory.ingest(namespace,source_type="synthetic-recipe",content="User prefers a missing model to fail safely.")
    failed = memory.extract_candidates(namespace,batch_id=batch.id,extractor="ollama_style")
    assert not memory.list_candidates(namespace,extraction_run_id=failed.id), "Missing model produced candidates"
    os.environ["ALETHEIA_LLM_OLLAMA_STYLE_MODEL"] = selected
    secret = memory.ingest(namespace,source_type="synthetic-recipe",content="Synthetic secret must never reach inference.",privacy_level="secret")
    blocked = memory.extract_candidates(namespace,batch_id=secret.id,extractor="ollama_style")
    assert not memory.list_candidates(namespace,extraction_run_id=blocked.id), "Secret source produced candidates"
    assert len(memory.list_claims(namespace=namespace)) == active_before
    return {"status":"passed" if all(run["status"] == "passed" for run in runs) else "failed",
        "samples":runs,"candidates":candidates,"new_active_claims":0,
        "checks":["three real structured outputs with exact evidence spans","pending candidates only","missing model fails without fallback","secret evidence remains blocked"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-local-models",action="store_true",help="Explicitly allow synthetic input to the selected loopback runtime.")
    parser.add_argument("--task",choices=["embedding","llm","all"],default="all")
    parser.add_argument("--base-url",default="http://127.0.0.1:11434")
    parser.add_argument("--embedding-model",default="nomic-embed-text:latest")
    parser.add_argument("--llm-model",choices=list(LLM_DIGESTS),default="llama3.1:8b")
    parser.add_argument("--report",type=Path)
    args = parser.parse_args()
    if not args.allow_local_models:
        parser.error("Explicit --allow-local-models is required. The default recipes may load about 5.2 GB of installed model weights plus runtime memory; no downloads are performed.")
    if args.report and (args.report.exists() or args.report.is_symlink()):
        parser.error("Report already exists. Choose a new path; no inference attempted.")
    base = args.base_url.rstrip("/")
    opener = local_opener(base)
    def get(path):
        with opener.open(Request(base+path),timeout=5) as response:
            return json.load(response)
    models = get("/api/tags")["models"]
    required = [(args.embedding_model,EMBEDDING_DIGEST)] if args.task == "embedding" else [(args.llm_model,LLM_DIGESTS[args.llm_model])] if args.task == "llm" else [(args.embedding_model,EMBEDDING_DIGEST),(args.llm_model,LLM_DIGESTS[args.llm_model])]
    selected = []
    for name,digest in required:
        match = next((model for model in models if model["name"] == name and model["digest"] == digest),None)
        if match is None:
            raise SystemExit(f"Expected local model {name} with the documented digest. Install it deliberately or revalidate a changed model; no inference attempted.")
        selected.append({key:match[key] for key in ["name","digest","size","details"]})
    configuration = configure(base,args.embedding_model,args.llm_model)
    report = {"status":"running","tested_at":datetime.now(timezone.utc).isoformat(),"software_version":software_version(),
        "python":platform.python_version(),"platform":platform.platform(),"ollama_version":get("/api/version")["version"],
        "models":selected,"configuration":configuration,"input":"Fixed synthetic examples only","downloaded_bytes":0,
        "limitations":"Smoke checks, not a quality benchmark. Local runtime is trusted; namespaces/privacy still govern Memory. No hosted fallback."}
    peak, stop = {}, threading.Event()
    def sample_memory():
        while not stop.wait(.2):
            try:
                for model in get("/api/ps").get("models",[]):
                    if model.get("name") in {name for name,_ in required}:
                        peak[model["name"]] = max(peak.get(model["name"],0),model.get("size_vram",0))
            except (OSError,ValueError):
                pass
    monitor = threading.Thread(target=sample_memory,daemon=True)
    monitor.start()
    started = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="aletheia-live-recipe-") as directory:
            memory = Memory.open(str(Path(directory)/"synthetic.db"))
            try:
                if args.task in {"embedding","all"}:
                    report["embedding"] = embedding_checks(memory,base)
                if args.task in {"llm","all"}:
                    report["llm"] = llm_checks(memory)
            finally:
                memory.close()
        report["status"] = "failed" if any(report.get(task, {}).get("status") == "failed" for task in ("embedding", "llm")) else "passed"
    except Exception as error:
        report.update(status="failed",failure=f"{type(error).__name__}: {error}")
    finally:
        stop.set()
        monitor.join(timeout=6)
    report.update(seconds=round(time.perf_counter()-started,3),sampled_peak_model_vram_bytes=peak)
    rendered = json.dumps(report,indent=2,sort_keys=True)+"\n"
    if args.report:
        with args.report.open("x",encoding="utf-8") as output:
            output.write(rendered)
    print(rendered,end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
