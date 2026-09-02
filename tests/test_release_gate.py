from __future__ import annotations

from scripts.release_gate import (
    disallowed_product_files,
    relative_markdown_links,
    target_is_generic_baseline,
)


def test_release_gate_detects_product_specific_paths_for_main():
    paths = [
        "aletheia/core/memory.py",
        "aletheia/integrations/sample_adapter.py",
        "tests/fixtures/sample_adapter/recall_request.json",
        "tests/test_sample_adapter_compatibility.py",
    ]

    assert target_is_generic_baseline(branch="main")
    assert target_is_generic_baseline(base_ref="main")
    assert disallowed_product_files(paths) == [
        "aletheia/integrations/sample_adapter.py",
        "tests/fixtures/sample_adapter/recall_request.json",
        "tests/test_sample_adapter_compatibility.py",
    ]


def test_release_gate_allows_product_specific_paths_off_main():
    assert not target_is_generic_baseline(branch="codex/sample_adapter-compatibility-layer")


def test_release_gate_rejects_relative_readme_links_for_pypi():
    markdown = (
        "[docs](docs/index.md) ![logo](assets/logo.svg) "
        "[section](#section) [site](https://example.com)"
    )

    assert relative_markdown_links(markdown) == ["assets/logo.svg", "docs/index.md"]
