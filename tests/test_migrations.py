"""Verify Alembic migration chain is intact."""
import subprocess
import sys


def test_migration_chain_has_initial_schema():
    """000_initial_schema must exist as a .py file in migrations/versions."""
    import os
    versions_dir = "migrations/versions"
    files = os.listdir(versions_dir)
    has_000 = any(f.startswith("000_") for f in files)
    assert has_000, "Missing 000_initial_schema migration"


def test_001_has_correct_down_revision():
    """001 migration must point to 000 as its parent."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migration_001",
        "migrations/versions/001_add_slack_webhook_url_to_team.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.down_revision == "000", (
        f"Expected down_revision='000', got {mod.down_revision!r}"
    )
