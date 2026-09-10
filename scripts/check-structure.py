#!/usr/bin/env python3
"""Fail if a plugin's manifest, frontmatter, or cross-references are malformed."""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin/marketplace.json"
PLUGINS = ROOT / "plugins"


def frontmatter(path):
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def check_manifests(problems):
    market = json.loads(MARKETPLACE.read_text())
    entries = {e["name"]: e for e in market["plugins"]}

    plugin_dirs = sorted(
        d for d in PLUGINS.iterdir() if d.is_dir() and not d.name.startswith(".")
    )
    for d in plugin_dirs:
        manifest_path = d / ".claude-plugin/plugin.json"
        if not manifest_path.is_file():
            problems.append(f"missing manifest: {manifest_path.relative_to(ROOT)}")
            continue
        manifest = json.loads(manifest_path.read_text())
        name = manifest.get("name")
        version = manifest.get("version")
        entry = entries.get(name)
        if entry is None:
            problems.append(f"plugin absent from marketplace: {name}")
            continue
        if entry.get("version") != version:
            problems.append(
                f"version drift: {name} plugin.json={version} marketplace={entry.get('version')}"
            )

    for entry in market["plugins"]:
        source = (ROOT / entry["source"]).resolve()
        if not source.is_dir():
            problems.append(
                f"marketplace entry with no plugin: {entry['name']} -> {entry['source']}"
            )


def check_frontmatter(problems):
    agent_names = {}  # name -> list of files

    for path in sorted(PLUGINS.glob("*/agents/*.md")):
        fm = frontmatter(path)
        rel = path.relative_to(ROOT)
        if "name" not in fm:
            problems.append(f"missing required frontmatter key 'name': {rel}")
        else:
            agent_names.setdefault(fm["name"], []).append(rel)
        if "description" not in fm:
            problems.append(f"missing required frontmatter key 'description': {rel}")
        tools = fm.get("tools")
        if tools is not None and tools.startswith("["):
            problems.append(f"array-form tools field: {rel} tools={tools}")

    for path in sorted(PLUGINS.glob("*/skills/*/SKILL.md")):
        fm = frontmatter(path)
        rel = path.relative_to(ROOT)
        if "name" not in fm:
            problems.append(f"missing required frontmatter key 'name': {rel}")
        if "description" not in fm:
            problems.append(f"missing required frontmatter key 'description': {rel}")

    for path in sorted(PLUGINS.glob("*/commands/*.md")):
        fm = frontmatter(path)
        rel = path.relative_to(ROOT)
        if "description" not in fm:
            problems.append(f"missing required frontmatter key 'description': {rel}")

    for name, files in sorted(agent_names.items()):
        if len(files) > 1:
            names = ", ".join(str(f) for f in files)
            problems.append(f"duplicate agent name '{name}': {names}")


def main():
    problems = []
    check_manifests(problems)
    check_frontmatter(problems)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
