import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone


class HarnessError(RuntimeError):
    """Сломался прогон, а не измеряемое поведение."""


class NoTestFiles(HarnessError):
    """Glob для `node --test` пуст — отдельный тип, чтобы отличить это от прочих
    поломок раннера (например, ненулевого кода без единой строки TAP)."""


def workspaces_from_result(result):
    case = result["cases"][0]
    runs = (case.get("arms") or {}).get("with")
    if not runs:
        raise HarnessError(f"в результате нет арма 'with' для кейса {case.get('name')!r}")
    out = []
    for run in runs:
        trace = run.get("tracePath") or ""
        if not trace.endswith("/out/trace.jsonl"):
            raise HarnessError(f"не распознан tracePath: {trace!r}")
        root = pathlib.Path(trace).parent.parent
        out.append(root / "sealed" / "home" / "cwd")
    return out


def require_existing(workspace):
    if workspace.is_dir():
        return workspace
    sealed = next((d for d in workspace.parents
                   if d.exists() and not os.access(d, os.X_OK)), None)
    if sealed is not None:
        raise HarnessError(
            f"рабочее дерево запечатано: {workspace}. "
            f"Снять печать: chmod 700 {sealed}")
    raise HarnessError(
        f"рабочее дерево не найдено: {workspace}. "
        "Прогон фазы 1 должен запускаться с сохранением временных файлов.")


# Каталог плагина: .../plugins/plan-flow/evals/e2e/run_e2e.py -> .../plugins/plan-flow
PLUGIN_DIR = pathlib.Path(__file__).resolve().parents[2]
RESULTS_DIR = PLUGIN_DIR / "evals" / "results"

# `claude -p` для фазы 2 не документирует собственный лимит; вложенные диспетчи внутри
# execute-plan делают её дольше фазы 1, поэтому запас больше, чем `timeout_seconds` кейса.
PHASE2_TIMEOUT_SECONDS = 1800

# Формулировки остановки из agents/plan-executor.md и commands/execute-plan.md —
# по ним и распознаём halted, а не по догадке о тексте отчёта.
_HALT_MARKERS = (
    "not yours to resolve",
    "bring it to the plan's author",
    "halts on a frozen-section conflict",
    "status: blocked",
)


def find_plan(workspace):
    plans = sorted((workspace / "docs" / "plans").glob("*.md")) if (workspace / "docs" / "plans").is_dir() else []
    plans += sorted((workspace / "docs" / "plans").glob("*/plan.md")) if (workspace / "docs" / "plans").is_dir() else []
    if not plans:
        return None
    return max(plans, key=lambda p: p.stat().st_mtime)


def parse_tap(text):
    tests = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("ok "):
            tests.append({"name": line.split("- ", 1)[-1], "ok": True})
        elif line.startswith("not ok "):
            tests.append({"name": line.split("- ", 1)[-1], "ok": False})
    return tests


def tap_result_or_raise(returncode, stdout, context):
    """Разбирает TAP; ненулевой код без единой строки TAP — харнесс не поднялся, не измеряемое поведение."""
    tests = parse_tap(stdout)
    if returncode != 0 and not tests:
        raise HarnessError(f"тестраннер не поднялся в {context}: код {returncode}")
    return tests


def run_node_tap(cwd, glob_pattern):
    # Явные пути вместо `node --test <pattern>`: subprocess не запускает шелл, и с node 21+
    # позиционный аргумент без раскрытия шеллом читается как имя модуля, а не как маска.
    files = sorted(str(p.relative_to(cwd)) for p in cwd.glob(glob_pattern))
    if not files:
        raise NoTestFiles(f"ни одного файла не найдено по маске {glob_pattern!r} в {cwd}")
    cmd = ["node", "--test", "--test-reporter=tap", *files]
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return tap_result_or_raise(done.returncode, done.stdout, f"{cwd} ({glob_pattern})")


def score_tests(tests):
    passed = sum(1 for t in tests if t["ok"])
    total = len(tests)
    return passed, total - passed, total


def copy_workspace(workspace, dest):
    """Снимает печать с запечатанного предка (если есть), копирует дерево в dest, печатает обратно."""
    sealed = None
    try:
        require_existing(workspace)
    except HarnessError:
        sealed = next((d for d in workspace.parents
                        if d.exists() and not os.access(d, os.X_OK)), None)
        if sealed is None:
            raise
        os.chmod(sealed, 0o700)
    try:
        if sealed is not None:
            require_existing(workspace)
        shutil.copytree(workspace, dest)
    finally:
        if sealed is not None:
            os.chmod(sealed, 0o000)
    return dest


def run_phase1(case, runs, plugin_dir, out_json):
    # Exit code reflects the case's own graders, not harness health — a red grader
    # must not abort the run; `_raise_on_run_start_failures` is the real gate.
    cmd = ["claude", "plugin", "eval", ".", "--case", case, "--tag", "e2e",
           "--ablation", "none", "--scaffold", "--allow-tools", "Write", "Edit",
           "--runs", str(runs), "--keep-temp", "--no-publish", "--json", str(out_json)]
    subprocess.run(cmd, cwd=plugin_dir)
    try:
        result = json.loads(out_json.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HarnessError(f"фаза 1 не поднялась для кейса {case!r}: нет отчёта в {out_json}") from exc
    _raise_on_run_start_failures(case, result)
    return result


def _raise_on_run_start_failures(case, result):
    """Raises only when a run never started (non-null `error`, per the runner's own
    report) — grader verdicts on a run that did start are a scored result, not this."""
    cases = result.get("cases") or [{}]
    runs = (cases[0].get("arms") or {}).get("with") or []
    errors = [run["error"] for run in runs if run.get("error")]
    if errors:
        raise HarnessError(
            f"фаза 1: прогон(ы) кейса {case!r} не запустились: {'; '.join(errors)}")


def phase1_total_cost(result):
    case = result["cases"][0]
    runs = (case.get("arms") or {}).get("with") or []
    costs = [r["costUsd"] for r in runs if r.get("costUsd") is not None]
    return sum(costs) if costs else None


def _reads_as_halt(text):
    lowered = (text or "").lower()
    return any(marker in lowered for marker in _HALT_MARKERS)


# Of the CLI's error subtypes (SDK bundle), only these two mean the agent ran and spent
# real turns/cost against its own ceiling; the rest reflect no completed agent work.
_EXHAUSTED_SUBTYPES = ("error_max_turns", "error_max_budget_usd")


def run_phase2(workspace, plan_path, plugin_dir, timeout, raw_response_path):
    cmd = ["claude", "-p", "--plugin-dir", str(plugin_dir),
           "--allowedTools", "Bash", "Write", "Edit", "Agent", "Read",
           "--permission-mode", "acceptEdits", "--output-format", "json",
           f"/plan-flow:execute-plan {plan_path}"]
    try:
        done = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "cost_usd": None, "turns": None, "text": ""}

    try:
        payload = json.loads(done.stdout) if done.stdout else None
    except json.JSONDecodeError:
        payload = None

    # Kept beside the report, outside its frozen shape — otherwise a strange phase 2 leaves
    # nothing to inspect afterwards.
    raw_response_path.write_text(json.dumps(
        {"returncode": done.returncode, "stdout": done.stdout, "stderr": done.stderr},
        indent=2, ensure_ascii=False) + "\n")

    if done.returncode != 0 or not isinstance(payload, dict):
        raise HarnessError(
            f"фаза 2 не поднялась в {workspace}: код {done.returncode}, "
            f"сырой ответ сохранён в {raw_response_path}")

    subtype = payload.get("subtype")
    if subtype in _EXHAUSTED_SUBTYPES:
        # No `result` text on this variant — the run hit its own ceiling mid-turn, it did
        # not report back like a completed one. Test score is computed the same as `timeout`.
        return {"status": "exhausted", "cost_usd": payload.get("total_cost_usd"),
                "turns": payload.get("num_turns"), "text": ""}

    # `result` text only exists under subtype "success"; any other subtype means phase 2
    # never produced a completion — not that it produced an empty one.
    if subtype != "success":
        raise HarnessError(
            f"фаза 2 не поднялась в {workspace}: код {done.returncode}, "
            f"сырой ответ сохранён в {raw_response_path}")

    text = payload.get("result", "")
    status = "halted" if _reads_as_halt(text) else "ok"
    return {"status": status, "cost_usd": payload.get("total_cost_usd"),
            "turns": payload.get("num_turns"), "text": text}


def run_single(dest, sealed_source, acceptance_dir, plugin_dir):
    plan_path = find_plan(dest)
    if plan_path is None:
        return ({"workspace": str(dest), "plan_path": None,
                 "phase2": {"status": "skipped"}, "score": 0.0},
                sealed_source, False, None)

    relative_plan = plan_path.relative_to(dest)
    raw_response_path = dest.parent / f"{dest.name}.phase2-response.json"
    phase2 = run_phase2(dest, relative_plan, plugin_dir, PHASE2_TIMEOUT_SECONDS, raw_response_path)

    shutil.copytree(acceptance_dir, dest / "acceptance", dirs_exist_ok=True)
    acceptance_tests = run_node_tap(dest, "acceptance/*.test.js")
    try:
        fixture_tests = run_node_tap(dest, "test/*.test.js")
        fixture_suite_missing = False
    except NoTestFiles:
        # Deleted by the agent — flagged separately since {} alone reads as zero tests.
        fixture_tests = []
        fixture_suite_missing = True
    except HarnessError:
        # Fixture's own runner broke (e.g. a syntax error) — still the agent's file, not ours.
        fixture_tests = []
        fixture_suite_missing = False

    passed, failed, total = score_tests(acceptance_tests)
    fx_passed, fx_failed, _ = score_tests(fixture_tests)
    run_score = passed / total if total else 0.0

    record = {
        "workspace": str(dest),
        "plan_path": str(relative_plan),
        "phase2": {"status": phase2["status"], "cost_usd": phase2["cost_usd"], "turns": phase2["turns"]},
        "acceptance": {"passed": passed, "failed": failed, "total": total, "tests": acceptance_tests},
        "fixture_tests": {"passed": fx_passed, "failed": fx_failed},
        "score": run_score,
    }
    # A timeout never reaches the write in run_phase2 — nothing to point to.
    written_raw_path = raw_response_path if phase2["status"] != "timeout" else None
    return record, sealed_source, fixture_suite_missing, written_raw_path


def compute_report(case, started_at, runs, phase1_cost_usd):
    scores = [r["score"] for r in runs]
    score = sum(scores) / len(scores) if scores else 0.0
    pass_rate = (sum(1 for s in scores if s == 1.0) / len(scores)) if scores else 0.0
    phase2_costs = [r["phase2"]["cost_usd"] for r in runs
                     if r["phase2"].get("cost_usd") is not None]
    phase2_cost_usd = sum(phase2_costs) if phase2_costs else None
    return {
        "case": case,
        "started_at": started_at,
        "score": score,
        "pass_rate": pass_rate,
        "phase1_cost_usd": phase1_cost_usd,
        "phase2_cost_usd": phase2_cost_usd,
        "runs": runs,
    }


def render_summary(report, sealed_sources, fixture_suite_missing=None, phase2_raw_paths=None):
    if fixture_suite_missing is None:
        fixture_suite_missing = [False] * len(report["runs"])
    if phase2_raw_paths is None:
        phase2_raw_paths = [None] * len(report["runs"])
    lines = [
        f"# {report['case']}",
        "",
        f"- started: {report['started_at']}",
        f"- score: {report['score']:.3f}",
        f"- pass rate: {report['pass_rate']:.3f}",
        "- phase1 cost: " + (f"${report['phase1_cost_usd']:.4f}" if report['phase1_cost_usd'] is not None else "n/a"),
        "- phase2 cost: " + (f"${report['phase2_cost_usd']:.4f}" if report['phase2_cost_usd'] is not None else "n/a"),
        "",
        "## Runs",
        "",
    ]
    for i, (run, sealed_source, suite_missing, raw_path) in enumerate(
            zip(report["runs"], sealed_sources, fixture_suite_missing, phase2_raw_paths), start=1):
        status = run["phase2"]["status"]
        note = ""
        acceptance = run.get("acceptance")
        fixture = run.get("fixture_tests")
        if suite_missing:
            note = " — regression: fixture test suite missing (agent deleted test/*.test.js)"
        elif acceptance and fixture and fixture["failed"] > 0 and acceptance["failed"] == 0:
            note = " — regression: fixture tests red while acceptance is green"
        lines.append(
            f"{i}. plan: {run['plan_path'] or 'none'} — phase2: {status} — score: {run['score']:.3f}{note}\n"
            f"   sealed: {sealed_source}\n"
            f"   copy: {run['workspace']}"
            + (f"\n   phase2 raw: {raw_path}" if raw_path is not None else "")
        )
    return "\n".join(lines) + "\n"


def write_report(out_dir, report, sealed_sources, fixture_suite_missing=None, phase2_raw_paths=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "e2e-result.json"
    result_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    summary_path = out_dir / "summary.md"
    summary_path.write_text(render_summary(report, sealed_sources, fixture_suite_missing, phase2_raw_paths))
    return result_path, summary_path


def timestamp_dir_name():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H-%M-%S-") + f"{now.microsecond // 1000:03d}Z"


def run_case(args):
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_dir = pathlib.Path(args.out) if args.out else RESULTS_DIR / f"e2e-{timestamp_dir_name()}"

    if args.phase1_json:
        phase1_result = json.loads(pathlib.Path(args.phase1_json).read_text())
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        phase1_result = run_phase1(args.case, args.runs, PLUGIN_DIR, out_dir / "phase1.json")

    sealed_workspaces = workspaces_from_result(phase1_result)
    phase1_cost_usd = phase1_total_cost(phase1_result)
    acceptance_dir = PLUGIN_DIR / "evals" / args.case / "acceptance"

    runs = []
    sealed_sources = []
    fixture_suite_missing = []
    phase2_raw_paths = []
    for i, sealed_workspace in enumerate(sealed_workspaces, start=1):
        dest = out_dir / f"ws-{i}"
        copy_workspace(sealed_workspace, dest)
        run_record, sealed_source, suite_missing, raw_path = run_single(
            dest, sealed_workspace, acceptance_dir, PLUGIN_DIR)
        runs.append(run_record)
        sealed_sources.append(sealed_source)
        fixture_suite_missing.append(suite_missing)
        phase2_raw_paths.append(raw_path)

    report = compute_report(args.case, started_at, runs, phase1_cost_usd)
    write_report(out_dir, report, sealed_sources, fixture_suite_missing, phase2_raw_paths)
    return report


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Три фазы сквозного eval-тира plan-flow")
    parser.add_argument("--case", required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--phase1-json", default=None)
    parser.add_argument("--out", default=None)
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        report = run_case(args)
    except HarnessError as exc:
        print(f"harness error: {exc}", file=sys.stderr)
        return 2
    print(f"case={report['case']} score={report['score']:.3f} pass_rate={report['pass_rate']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
