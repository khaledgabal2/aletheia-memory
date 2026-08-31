"""Execute installed onboarding artifacts outside the checkout (stdlib runner).

Usage: python scripts/v1_4_onboarding_check.py --python /fresh/venv/bin/python
Install a built wheel or sdist into that environment first, without dev extras.
This measures automated execution only, not installation or human review time.
"""
import argparse
from contextlib import redirect_stdout
from importlib import metadata
from importlib.resources import files
import io
import json
import os
from pathlib import Path
import re
import runpy
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


def worker():
    import aletheia
    from aletheia.help import docs_root, find_help_document
    from aletheia.onboarding import create_starter
    from aletheia.diagnostics import diagnose

    started = time.perf_counter()
    checks = []
    package = Path(aletheia.__file__).resolve().parent
    assert "site-packages" in package.parts, f"Expected an installed artifact, got {package}"
    assert docs_root().resolve() == package / "docs"
    assert not any(metadata.packages_distributions().get(name) for name in ("pytest", "openai", "torch", "transformers"))
    checks.append("installed core-only artifact with packaged docs")
    source = files("aletheia").joinpath("starters", "embedded", "memory_demo.py").read_text()
    document = Path(find_help_document("quickstart").path).read_text()
    block = re.search(r"```python\n(.*?)\n```", document, re.S).group(1)
    assert block == source.strip()
    checks.append("installed quickstart matches packaged source")

    def no_network(*args, **kwargs):
        raise AssertionError("Zero-model flow attempted a network connection")

    def state(db, approved, *, http=False):
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            assert connection.execute("SELECT count(*) FROM claims WHERE status IN ('active','core')").fetchone()[0] == int(approved)
            assert connection.execute("SELECT count(*) FROM candidate_claims WHERE candidate_status='pending_review'").fetchone()[0] == int(not approved)
            if http:
                assert connection.execute("SELECT count(*) FROM api_tokens WHERE revoked_at IS NULL").fetchone()[0] == 0

    for origin in ("documentation", "embedded"):
        for answer in ("approve", "decline", ""):
            path = Path(origin + "-" + (answer or "eof"))
            if origin == "embedded":
                create_starter("embedded", path)
            else:
                path.mkdir()
                (path / "memory_demo.py").write_text(block)
            assert not list(path.glob("*.db"))
            script = (path / "memory_demo.py").resolve()
            previous = Path.cwd()
            os.chdir(path)
            try:
                output = io.StringIO()
                with patch.object(socket.socket, "connect", no_network), patch.object(socket.socket, "connect_ex", no_network), patch("builtins.input", return_value=answer), redirect_stdout(output):
                    runpy.run_path(str(script), run_name="__main__")
                text = output.getvalue()
                assert "Trusted results before approval: 0" in text
                assert "Source: User prefers careful architecture notes." in text
                assert ("Reopened successfully" in text) == (answer == "approve")
                if answer == "approve":
                    assert "Provenance: User prefers careful architecture notes." in text
                db = Path("aletheia-demo.db")
                state(db, answer == "approve")
                before = db.read_bytes()
                try:
                    runpy.run_path(str(script), run_name="__main__")
                except SystemExit as error:
                    assert "already exists" in str(error)
                else:
                    raise AssertionError("Demo accepted an existing database")
                assert db.read_bytes() == before
                with patch.object(socket.socket, "connect", no_network):
                    report = diagnose(db_path=str(db), namespace="user/demo", query="architecture")
                codes = {item["code"] for item in report["checks"]}
                assert ("lexical_match" if answer == "approve" else "pending_review") in codes
                assert db.read_bytes() == before
            finally:
                os.chdir(previous)
            checks.append(f"{origin}: {answer or 'empty input'}, offline, persistence, safe rerun, read-only diagnosis")

    for answer in ("approve", "decline"):
        path = Path("http-" + answer)
        generated = subprocess.run([sys.executable, "-I", "-c", "from aletheia.cli.main import main; raise SystemExit(main())", "examples", "create", "--type", "http-agent", "--output", str(path)], capture_output=True, text=True, timeout=15)
        assert generated.returncode == 0, generated.stderr
        assert not list(path.glob("*.db"))
        result = subprocess.run([sys.executable, "-I", str((path / "operator_demo.py").resolve())], cwd=path, input=answer + "\n", capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stderr
        assert "Visible context items: 0" in result.stdout
        assert ("Reopened successfully" in result.stdout) == (answer == "approve")
        if answer == "approve":
            assert "Visible context items: 1" in result.stdout and "Provenance:" in result.stdout
        state(path / "aletheia-http-demo.db", answer == "approve", http=True)
        before = {file.name: file.read_bytes() for file in path.iterdir() if file.is_file()}
        again = subprocess.run([sys.executable, "-I", "-c", "from aletheia.cli.main import main; raise SystemExit(main())", "examples", "create", "--type", "http-agent", "--output", str(path)], capture_output=True, text=True, timeout=15)
        assert again.returncode != 0 and "already exists" in again.stderr
        assert before == {file.name: file.read_bytes() for file in path.iterdir() if file.is_file()}
        checks.append(f"HTTP: {answer}, separate scoped agent, explicit review, persistence, revoked tokens, safe generation")

    missing = Path("missing") / "memory.db"
    result = subprocess.run([sys.executable, "-I", "-c", "from aletheia.cli.main import main; raise SystemExit(main())", "doctor", "--read-only", "--db", str(missing)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and "database_missing" in result.stdout
    assert not missing.parent.exists()
    checks.append("installed CLI diagnoses missing database without creating its parent")
    print(json.dumps({"status": "passed", "python": sys.version.split()[0], "package_version": metadata.version("aletheia-memory"),
        "checks": checks, "automated_execution_seconds": round(time.perf_counter() - started, 3),
        "installation_time": "measured separately", "human_five_minute_walkthrough": "not measured",
        "network_scope": "embedded/documentation socket connections blocked; HTTP uses a disposable loopback service"}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", help="Python executable in a fresh core-only artifact environment")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker()
        return
    if not args.python:
        parser.error("--python is required")
    # Resolving a venv executable symlink can select the base interpreter instead.
    target = str(Path(args.python).absolute())
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH") if key in os.environ}
    environment["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryDirectory(prefix="aletheia-installed-onboarding-") as directory:
        result = subprocess.run([target, "-I", str(Path(__file__).resolve()), "--worker"], cwd=directory, env=environment, timeout=180)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
