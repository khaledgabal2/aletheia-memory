"""Upgrade and recover a database made by the actual published 1.3.1 binary."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from aletheia import Memory
from aletheia.storage import SCHEMA_VERSION
from aletheia.storage.review import integrity

CHILD = r'''
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
from aletheia import Memory
from aletheia.service.auth import AuthService
from aletheia.core.hardening import restore_backup
assert pathlib.Path(__import__('aletheia').__file__).is_relative_to(pathlib.Path(sys.argv[1]))
action, path, archive = sys.argv[2:5]
namespace = 'user/migration-fixture'
if action == 'refuse':
    try:
        memory = Memory.open(path)
    except RuntimeError as error:
        assert 'newer than supported schema' in str(error)
    else:
        memory.close()
        raise AssertionError('Older binary accepted the new storage version')
    print('Older binary refused upgraded storage')
else:
    if action == 'recover':
        restore_backup(backup_path=archive, target_db_path=path, mode='new_database',
            passphrase='synthetic-migration-password', dry_run=False)
    memory = Memory.open(path)
    try:
        if action == 'seed':
            memory.remember(namespace=namespace, memory_type='preference', subject='user',
                predicate='prefers', object='careful architecture notes', source_type='manual')
            batch = memory.ingest(namespace, source_type='manual', content='User prefers compact review summaries.')
            memory.extract_candidates(namespace, batch_id=batch.id)
            auth = AuthService(memory)
            client = auth.create_client(name='migration-fixture', client_type='test')
            auth.create_token(client_id=client.id, namespace_grants=[namespace], capabilities=['memory:read'])
        assert memory.health()['schema_version'] == '1.3.0'
        assert memory.retrieve(namespace, query='architecture', mode='lexical')
        assert memory.context_pack(namespace, query='architecture', retrieval_mode='lexical').sources
        assert len(memory.list_candidates(namespace)) == 1
        tables = ['claims', 'evidence_events', 'claim_evidence_links', 'candidate_claims', 'candidate_evidence_links',
            'api_clients', 'api_tokens', 'capability_grants', 'namespace_access_grants']
        import hashlib
        print(json.dumps({table: hashlib.sha256(repr([tuple(row) for row in memory.store.connection.execute('SELECT * FROM '+table+' ORDER BY rowid')]).encode()).hexdigest() for table in tables}, sort_keys=True))
    finally:
        memory.close()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-package", type=Path, required=True)
    args = parser.parse_args()
    package = args.legacy_package.resolve()
    root = Path(__file__).resolve().parents[1]
    provenance = json.loads((root / "tests/fixtures/v1_3_1/provenance.json").read_text())
    for name, expected in provenance["runtime_sha256"].items():
        assert hashlib.sha256(package.joinpath(*name.split(".")).with_suffix(".py").read_bytes()).hexdigest() == expected
    with tempfile.TemporaryDirectory(prefix="aletheia-migration-") as directory:
        path, archive = Path(directory) / "legacy.db", Path(directory) / "before.alet"
        def legacy(action, database):
            result = subprocess.run([sys.executable, "-I", "-c", CHILD, str(package), action, str(database), str(archive)],
                text=True, capture_output=True, timeout=45)
            if result.returncode:
                raise RuntimeError(f"Published binary {action} failed: {result.stderr}")
            return result.stdout.strip()
        before = json.loads(legacy("seed", path))
        subprocess.run([sys.executable, "-c", "from aletheia.cli.main import main; raise SystemExit(main())", "migrate", "apply", "--db", str(path),
            "--backup-before", "--backup-output", str(archive), "--passphrase", "synthetic-migration-password"],
            check=True, capture_output=True, text=True, timeout=45)
        memory = Memory.open(str(path), auto_migrate=False)
        try:
            assert memory.health()["schema_version"] == SCHEMA_VERSION and integrity(memory.store.connection)
            after = {table: hashlib.sha256(repr([tuple(row) for row in memory.store.connection.execute('SELECT * FROM '+table+' ORDER BY rowid')]).encode()).hexdigest() for table in before}
            assert before == after
            assert memory.retrieve("user/migration-fixture", query="architecture", mode="lexical")
            assert memory.context_pack("user/migration-fixture", query="architecture", retrieval_mode="lexical").sources
        finally:
            memory.close()
        legacy("refuse", path)
        assert json.loads(legacy("recover", Path(directory) / "recovered.db")) == before
    print("Published 1.3.1 database: upgrade preserves claims, evidence, candidates, permissions and retrieval; older binary refuses new storage and recovers the encrypted pre-upgrade backup.")


if __name__ == "__main__":
    main()
