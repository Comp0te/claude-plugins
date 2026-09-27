#!/usr/bin/env python3
"""Fail if a plugin's manifest, frontmatter, or cross-references are malformed."""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin/marketplace.json"
PLUGINS = ROOT / "plugins"
REFERENCE_RE = re.compile(r"\b([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)\b")


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


def agent_tools(path):
    """Return the agent's `tools` as a list, or None when the field is absent."""
    lines = path.read_text().split("\n---", 1)[0].splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("tools:"):
            continue
        value = line.partition(":")[2].strip()
        if value:
            return [t.strip() for t in value.split(",") if t.strip()]
        tools = []
        for item in lines[i + 1 :]:
            if not item.lstrip().startswith("- "):
                break
            tools.append(item.lstrip()[2:].strip())
        return tools
    return None


# review-flow agents only report: none may write or spawn, and the verifiers
# judge from source alone. The reviewers keep Bash for `verified:` evidence.
REVIEW_FLOW_FORBIDDEN = {"Agent", "Task", "Write", "Edit", "NotebookEdit"}
REVIEW_FLOW_NO_BASH = {"finding-gate-verifier", "fix-verifier"}


def check_agent_tools(problems, paths=None):
    if paths is None:
        paths = sorted(PLUGINS.glob("review-flow/agents/*.md"))
    for path in paths:
        tools = agent_tools(path)
        if tools is None:
            problems.append(f"review-flow agent has no tools field, so inherits all: {path.name}")
            continue
        for tool in sorted(REVIEW_FLOW_FORBIDDEN.intersection(tools)):
            problems.append(f"review-flow agent granted {tool}: {path.name}")
        if path.stem in REVIEW_FLOW_NO_BASH and "Bash" in tools:
            problems.append(f"review-flow verifier granted Bash: {path.name}")


def check_cross_references(problems):
    local_plugins = sorted(
        d.name for d in PLUGINS.iterdir() if d.is_dir() and not d.name.startswith(".")
    )

    resolvable = set()
    for plugin in local_plugins:
        for path in (PLUGINS / plugin / "agents").glob("*.md"):
            fm = frontmatter(path)
            if "name" in fm:
                resolvable.add(f"{plugin}:{fm['name']}")
        for path in (PLUGINS / plugin / "commands").glob("*.md"):
            resolvable.add(f"{plugin}:{path.stem}")
        for path in (PLUGINS / plugin / "skills").glob("*/SKILL.md"):
            resolvable.add(f"{plugin}:{path.parent.name}")

    local_plugin_names = set(local_plugins)
    for path in sorted(PLUGINS.glob("**/*.md")):
        rel = path.relative_to(ROOT)
        text = path.read_text()
        for prefix, name in REFERENCE_RE.findall(text):
            if prefix not in local_plugin_names:
                continue
            ref = f"{prefix}:{name}"
            if ref not in resolvable:
                problems.append(f"dangling cross-reference: {ref} in {rel}")


def main():
    problems = []
    check_manifests(problems)
    check_frontmatter(problems)
    check_agent_tools(problems)
    check_cross_references(problems)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
