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
             ".harness/flow.py": SOURCE / "workflow.py",
             ".harness/coordination.py": SOURCE / "coordination.py",
             "AGENTS.md": SOURCE / "templates/task-AGENTS.md",
             ".harness/WORKFLOW_KO.md": SOURCE / "docs" / "WORKFLOW_KO.md",
             ".harness/GUIDE.md": SOURCE / "docs" / "SHARED_GUIDANCE.md",
             ".harness/START_HERE_KO.md": SOURCE / "docs" / "START_HERE_KO.md",
             ".harness/SOURCES.md": SOURCE / "SOURCES.md",
             ".harness/LICENSE": SOURCE / "LICENSE",
             ".harness/VERSION": SOURCE / "VERSION"}
    for p in sorted((SOURCE / ".agents/skills").rglob("*")):
        if p.is_file():
            files[p.relative_to(SOURCE).as_posix()] = p
    for folder in ("templates", "references", "examples"):
        for p in sorted((SOURCE / folder).rglob("*")):
            if p.is_file() and not any(x in p.parts for x in ("target", "__pycache__", ".venv")) and p.name != "classpath.txt":
                files[".harness/" + p.relative_to(SOURCE).as_posix()] = p
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
    if len([name for name in files if name.endswith("/SKILL.md")]) != 7:
        raise KitError("Expected seven bundled skills")
    plan, conflicts = [], []
    for relative, source in files.items():
        # Preserve supplied instructions. The user can explicitly point Codex at
        # hackathon-start in existing projects; never silently rewrite rules.
        if relative == 'AGENTS.md' and (target / relative).exists():
            safe_path(target, relative)
            if not (target / relative).is_file():
                raise KitError('AGENTS.md must be a regular file')
            print('KEEP   existing AGENTS.md (read hackathon-start explicitly once if it has no workflow entry)')
            continue
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
    print("Installed. Supplied project files are preserved; a workflow AGENTS.md was added only if absent.")
    print("Next: ask Codex to read .agents/skills/hackathon-start/SKILL.md and start; or python3 .harness/flow.py start.")
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
