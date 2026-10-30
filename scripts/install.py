#!/usr/bin/env python3
"""Preview an additive installation. Use --apply after reviewing the plan."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from harness import KitError, safe_path  # noqa: E402


def installation_files():
    files = {".harness/runner.py": SOURCE / "harness.py",
             ".harness/GUIDE.md": SOURCE / "docs" / "SHARED_GUIDANCE.md",
             ".harness/START_HERE_KO.md": SOURCE / "docs" / "START_HERE_KO.md",
             ".harness/SOURCES.md": SOURCE / "SOURCES.md",
             ".harness/LICENSE": SOURCE / "LICENSE",
             ".harness/VERSION": SOURCE / "VERSION"}
    for p in sorted((SOURCE / ".agents/skills").rglob("*")):
        if p.is_file():
            files[p.relative_to(SOURCE).as_posix()] = p
    return files


def install(target, apply=False):
    target = Path(target).absolute()
    if not target.is_dir() or target.is_symlink():
        raise KitError("Target must be an existing, non-symlink task directory")
    target = target.resolve()
    if target == SOURCE or SOURCE in target.parents or target == Path(target.anchor) or target == Path.home():
        raise KitError("Use a separate task workspace, not the kit, filesystem root, or home")
    manifest = json.loads((SOURCE / "release-manifest.json").read_text(encoding="utf-8"))
    files = installation_files()
    if len([name for name in files if name.endswith("/SKILL.md")]) != 4:
        raise KitError("Expected four bundled skills")
    plan, conflicts = [], []
    for relative, source in files.items():
        if source.is_symlink() or not source.is_file():
            raise KitError(f"Missing or symlink source: {source.name}")
        data = source.read_bytes()
        source_name = source.relative_to(SOURCE).as_posix()
        if manifest.get("sha256", {}).get(source_name) != hashlib.sha256(data).hexdigest():
            raise KitError(f"Release source has changed: {source_name}; inspect and rebuild its manifest")
        dest = safe_path(target, relative)
        if dest.exists():
            if not dest.is_file() or dest.read_bytes() != data:
                conflicts.append(relative)
            else:
                print(f"KEEP   {relative}")
        else:
            # Existing non-directory parents must fail before any write.
            for parent in dest.parents:
                if parent == target:
                    break
                if parent.exists() and not parent.is_dir():
                    conflicts.append(str(parent.relative_to(target)))
            plan.append((relative, dest, data))
    if conflicts:
        raise KitError("Conflicts; nothing written: " + ", ".join(sorted(set(conflicts))))
    for relative, _, _ in plan:
        print(f"{'CREATE' if apply else 'PLAN  '} {relative}")
    if not apply:
        print("Dry run. Re-run with --apply to create only the listed files.")
        return 0
    created = []
    try:
        for _, path, data in plan:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as f:
                f.write(data)
            created.append(path)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    print("Installed. Existing README, AGENTS.md, app code, configuration, and authentication were not changed.")
    print("Next: python3 .harness/runner.py init; then ask Codex to use $hackathon-intake.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(install(args.target, args.apply))
    except (KitError, OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
