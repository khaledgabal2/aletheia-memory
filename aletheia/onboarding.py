"""Internal helpers for safe CLI onboarding; not a second memory API."""

from importlib.resources import files
import os
from pathlib import Path

from aletheia.core.errors import ValidationError


STARTERS = {"embedded": ("memory_demo.py", "README.md"),
            "http-agent": ("agent.py", "operator_demo.py", "README.md"),
            "typescript-agent": ("agent.ts", "schema.d.ts", "package.json", "package-lock.json", "tsconfig.json", "README.md")}


def reserve_database(path):
    """Atomically reserve a new local file without following a final symlink."""
    if str(path) == ":memory:":
        raise ValidationError("--new requires a filesystem database path.")
    target = Path(path).expanduser()
    for suffix in ("-wal", "-shm", "-journal"):
        companion = Path(str(target) + suffix)
        if companion.exists() or companion.is_symlink():
            raise ValidationError("Database companion file already exists. Preserve it and choose a fresh path.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    except FileExistsError as exc:
        raise ValidationError("Database destination already exists. Choose a new path; nothing was overwritten.") from exc
    except OSError as exc:
        raise ValidationError("Cannot create the database. Check the parent directory and its permissions.") from exc
    return target


def write_new_project(output_path, content):
    target = Path(output_path).expanduser()
    try:
        # Reserve the whole project so no individual config/source file is replaced.
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ValidationError("Output directory already exists. Choose a new directory; existing files were left unchanged.") from exc
    except OSError as exc:
        raise ValidationError("Cannot create the output directory. Check its parent and permissions.") from exc
    try:
        for name, text in content.items():
            with (target / name).open("x", encoding="utf-8") as output:
                output.write(text)
    except OSError as exc:
        # Do not recursively delete a user's directory on failure.
        raise ValidationError("Project creation stopped. Inspect the partial directory before choosing a fresh destination.") from exc
    return target


def create_starter(kind, output_path):
    root = files("aletheia").joinpath("starters", kind)
    content = {name: root.joinpath(name).read_text(encoding="utf-8") for name in STARTERS[kind]}
    if kind == "typescript-agent":
        content["operator_demo.py"] = files("aletheia").joinpath("starters", "http-agent", "operator_demo.py").read_text(encoding="utf-8")
    content[".gitignore"] = "*.db\n*.db-*\n*.sqlite*\n.env\n.venv/\n__pycache__/\n"
    if kind == "typescript-agent":
        content[".gitignore"] += "node_modules/\ndist/\n"
    content["requirements.txt"] = "aletheia-memory>=1.3.1,<2\n" if kind == "embedded" else "aletheia-memory>=1.4.0,<2\n"
    target = write_new_project(output_path, content)
    return {"type": kind, "path": str(target), "files": sorted(content), "database_created": False}
