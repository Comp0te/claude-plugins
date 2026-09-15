import pathlib


class HarnessError(RuntimeError):
    """Сломался прогон, а не измеряемое поведение."""


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
    if not workspace.is_dir():
        raise HarnessError(
            f"рабочее дерево не найдено: {workspace}. "
            "Прогон фазы 1 должен запускаться с сохранением временных файлов.")
    return workspace
