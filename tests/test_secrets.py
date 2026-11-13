"""scripts/secrets.sh: listing never prints values; lookup prints exactly one."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "secrets.sh"


def run(tmp_path, *args):
    env = {**os.environ, "SECRETS_FILE": str(tmp_path / "env")}
    return subprocess.run([SCRIPT, *args], env=env, capture_output=True, text=True)


def test_list_hides_values_and_lookup_returns_one(tmp_path):
    (tmp_path / "env").write_text("# Planka bot key\nAPI_KEY=s3cret=with=equals\nEMPTY_ONE=\n")
    listing = run(tmp_path).stdout
    assert "s3cret" not in listing
    assert "API_KEY" in listing and "set" in listing and "Planka bot key" in listing
    assert "EMPTY" in listing
    assert run(tmp_path, "API_KEY").stdout == "s3cret=with=equals\n"
    missing = run(tmp_path, "EMPTY_ONE")
    assert missing.returncode == 1 and missing.stdout == ""
