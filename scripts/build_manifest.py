#!/usr/bin/env python3
"""Rebuild the kit's local installation integrity manifest after review."""
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from install import installation_files

files = installation_files()
manifest = {"version": (ROOT / "VERSION").read_text().strip(), "sha256": {
    path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in files.values()
}}
(ROOT / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Recorded {len(manifest['sha256'])} source hashes; this is integrity metadata, not a digital signature.")
