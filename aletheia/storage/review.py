"""Durable review invalidation at the SQLite boundary; no HTTP dependencies."""
from importlib.resources import files
import json
import uuid


def inventory():
    return json.loads(files("aletheia.storage.migrations").joinpath("review_tables.json").read_text())


def trigger_definitions():
    for table in inventory()["invalidates"]:
        for action in ("INSERT", "UPDATE", "DELETE"):
            name = f"review_epoch_{table}_{action.lower()}"
            yield name, (f"CREATE TRIGGER {name} AFTER {action} ON {table} BEGIN "
                         "UPDATE review_state SET epoch = epoch + 1 WHERE id = 1; END")


def install(connection):
    """Called only inside the complete schema migration transaction."""
    created = connection.execute("INSERT OR IGNORE INTO review_state (id, generation, epoch) VALUES (1, ?, 0)", (uuid.uuid4().hex,)).rowcount
    if not created:
        rotate_generation(connection)
    for name, sql in trigger_definitions():
        connection.execute(f"DROP TRIGGER IF EXISTS {name}")
        connection.execute(sql)


def integrity(connection):
    """Include coverage, trigger definitions and singleton shape in schema checks."""
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
              if not row[0].startswith(("sqlite_", "claims_fts"))}
    classified = inventory()
    if tables != set(classified["invalidates"]) | set(classified["excluded"]):
        return False
    rows = connection.execute("SELECT id, generation, epoch FROM review_state").fetchall()
    if len(rows) != 1 or rows[0][0] != 1 or not rows[0][1] or type(rows[0][2]) is not int or rows[0][2] < 0:
        return False
    actual = dict(connection.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'review_epoch_%'"))
    expected = dict(trigger_definitions())
    normalize = lambda sql: " ".join(sql.strip().rstrip(";").split())
    if set(actual) != set(expected) or any(normalize(actual[key]) != normalize(sql) for key, sql in expected.items()):
        return False
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_candidates_review_page'").fetchone() is not None


def rotate_generation(connection):
    """Restore/rollback must not resurrect inspected tokens or successful keys."""
    connection.execute("UPDATE review_state SET generation=?, epoch=epoch+1 WHERE id=1", (uuid.uuid4().hex,))
    connection.execute("DELETE FROM review_replays")
