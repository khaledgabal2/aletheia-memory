"""Software and protocol metadata, deliberately separate from storage versions."""

from importlib import metadata
from pathlib import Path
import tomllib


API_VERSION = "v1"
# Add a profile only after its complete conformance gate passes.
SUPPORTED_PROFILES: tuple[str, ...] = ("memory-read-v1",)
SUPPORTED_FEATURES = ("current-principal",)


def software_version() -> str:
    """Prefer installed build metadata; support a source checkout without a build."""
    try:
        return metadata.version("aletheia-memory")
    except metadata.PackageNotFoundError:
        return _source_version(Path(__file__).resolve().parents[1] / "pyproject.toml")


def _source_version(path: Path) -> str:
    try:
        project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
        if not isinstance(project, dict):
            return "0+unknown"
        value = project.get("version")
        if project.get("name") == "aletheia-memory" and isinstance(value, str) and value.strip():
            return value
    except (OSError, ValueError):
        pass
    # Never report the storage version as an invented software version.
    return "0+unknown"


def discovery_metadata() -> dict:
    return {
        "software_version": software_version(),
        "api_version": API_VERSION,
        "supported_profiles": list(SUPPORTED_PROFILES),
        "supported_features": list(SUPPORTED_FEATURES),
    }
