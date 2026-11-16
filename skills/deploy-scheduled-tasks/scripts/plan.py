#!/usr/bin/env python3
"""Plan a deployment of the scheduled tasks of manifest files.

Compares each entry of the manifests with its task in a saved response of the
action `list` of the API of the scheduled tasks. Prints the plan, and with
`--bodies` writes the call of each create or update to a JSON file, for any
client of the API to send.

Exits with status 1 and a message on a condition that stops the deployment.
"""

import argparse
import difflib
import json
import os
import tomllib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

REQUIRED = {
    "name": str,
    "schedule": str,
    "model": str,
    "prompt": str,
    "repositories": list,
    "environment_id": str,
    "enabled": bool,
}
OPTIONAL = {"effort": str, "chat_project_id": str}
COMPARED = tuple(name for name in REQUIRED | OPTIONAL if name != "name")
JOB_CONFIG = ("model", "prompt", "repositories", "environment_id", "effort")


@dataclass
class Entry:
    """A manifest entry. `values["prompt"]` is the text of its prompt file."""

    task_name: str
    values: dict
    prompt_path: str


@dataclass
class Outcome:
    entry: Entry
    action: str
    task: dict | None = None
    differences: list[str] = field(default_factory=list)
    call: dict | None = None
    call_file: str | None = None


def read_text(path: str, where: str) -> str:
    try:
        with open(path, encoding="utf-8") as file:
            return file.read()
    except (OSError, UnicodeDecodeError) as error:
        raise SystemExit(f"{where}: {error}") from error


def check_entry(entry: object, where: str) -> None:
    if not isinstance(entry, dict):
        raise SystemExit(f"{where}: an entry must be a table")
    missing = REQUIRED.keys() - entry.keys()
    unknown = entry.keys() - REQUIRED.keys() - OPTIONAL.keys()
    problems = [
        f"{label} fields {sorted(names)}"
        for label, names in (("missing", missing), ("unknown", unknown))
        if names
    ]
    if problems:
        raise SystemExit(f"{where}: {', '.join(problems)}")
    for name, kind in (REQUIRED | OPTIONAL).items():
        if name in entry and not isinstance(entry[name], kind):
            raise SystemExit(f"{where}: `{name}` must be a {kind.__name__}")
    if not all(isinstance(url, str) for url in entry["repositories"]):
        raise SystemExit(f"{where}: `repositories` must be a list of strings")


def read_manifest(path: str) -> list[Entry]:
    """Return the entries of the manifest at `path`."""
    try:
        data = tomllib.loads(read_text(path, path))
    except tomllib.TOMLDecodeError as error:
        raise SystemExit(f"{path}: invalid TOML: {error}") from error
    tables = data.get("task", [])
    if (
        data.keys() - {"namespace", "task"}
        or not isinstance(data.get("namespace"), str)
        or not isinstance(tables, list)
    ):
        raise SystemExit(
            f"{path}: a manifest must contain `namespace` and `[[task]]` tables only"
        )
    namespace, entries = data["namespace"], []
    for index, values in enumerate(tables, start=1):
        where = f"{path}, entry {index}"
        check_entry(values, where)
        prompt_path = os.path.join(os.path.dirname(path), values["prompt"])
        prompt = read_text(prompt_path, where).removesuffix("\n")
        entries.append(
            Entry(
                task_name=f"{namespace}: {values['name']}",
                values=values | {"prompt": prompt},
                prompt_path=prompt_path,
            )
        )
    return entries


def load_tasks(path: str) -> list[dict]:
    try:
        listing = json.loads(read_text(path, path))
    except json.JSONDecodeError as error:
        raise SystemExit(
            f"{path}: {error}. The file must contain the JSON response of `list` "
            "without the status line."
        ) from error
    if not isinstance(listing, dict) or not isinstance(listing.get("data"), list):
        raise SystemExit(f"{path}: the response of `list` must contain the list `data`")
    if listing.get("has_more"):
        raise SystemExit("the response of `list` sets `has_more` and omits tasks")
    return listing["data"]


def task_values(task: dict) -> dict:
    ccr = (task.get("job_config") or {}).get("ccr") or {}
    context = ccr.get("session_context") or {}
    derived = task.get("derived_state") or {}
    return {
        "schedule": task.get("cron_expression"),
        "model": derived.get("model"),
        "prompt": derived.get("prompt"),
        "repositories": [
            (source.get("git_repository") or {}).get("url")
            for source in context.get("sources") or []
        ],
        "environment_id": ccr.get("environment_id"),
        "enabled": task.get("enabled"),
        "effort": context.get("effort_level"),
        "chat_project_id": task.get("chat_project_id"),
    }


def differences(entry: Entry, task: dict) -> list[str]:
    values = task_values(task)
    found = [name for name in COMPARED if entry.values.get(name) != values[name]]
    if task.get("mcp_connections"):
        found.append("mcp_connections")
    return found


def job_config(entry: Entry) -> dict:
    values = entry.values
    context = {
        "model": values["model"],
        "sources": [{"git_repository": {"url": url}} for url in values["repositories"]],
    }
    if "effort" in values:
        context["effort_level"] = values["effort"]
    message = {"role": "user", "content": values["prompt"]}
    return {
        "ccr": {
            "environment_id": values["environment_id"],
            "session_context": context,
            "events": [
                {
                    "data": {
                        "uuid": str(uuid.uuid4()),
                        "session_id": "",
                        "type": "user",
                        "parent_tool_use_id": None,
                        "message": message,
                    }
                }
            ],
        }
    }


def create_call(entry: Entry) -> dict:
    body = {
        "name": entry.task_name,
        "cron_expression": entry.values["schedule"],
        "enabled": entry.values["enabled"],
        "clear_mcp_connections": True,
        "job_config": job_config(entry),
    }
    if "chat_project_id" in entry.values:
        body["chat_project_id"] = entry.values["chat_project_id"]
    return {"action": "create", "body": body}


def update_call(entry: Entry, task: dict, found: list[str]) -> dict:
    """Return an update of the differing fields. The body contains the whole
    `job_config`, because an update replaces the stored one."""
    body = {}
    if "schedule" in found:
        body["cron_expression"] = entry.values["schedule"]
    if "enabled" in found:
        body["enabled"] = entry.values["enabled"]
    if any(name in found for name in JOB_CONFIG):
        body["job_config"] = job_config(entry)
    if "mcp_connections" in found:
        body["clear_mcp_connections"] = True
    return {"action": "update", "trigger_id": task["id"], "body": body}


def make_plan(paths: list[str], tasks: list[dict]) -> list[Outcome]:
    """Compare the entries of the manifests at `paths` with `tasks`."""
    entries = [entry for path in paths for entry in read_manifest(path)]
    names = set()
    for entry in entries:
        if entry.task_name in names:
            raise SystemExit(f"two entries name the task `{entry.task_name}`")
        names.add(entry.task_name)
    by_name = {}
    for task in tasks:
        by_name.setdefault(task["name"], []).append(task)
    outcomes = []
    for entry in entries:
        matches = by_name.get(entry.task_name, [])
        if len(matches) > 1:
            ids = ", ".join(task["id"] for task in matches)
            raise SystemExit(f"the tasks {ids} share the name `{entry.task_name}`")
        if not matches:
            outcomes.append(Outcome(entry, "create", call=create_call(entry)))
            continue
        task = matches[0]
        found = differences(entry, task)
        if "chat_project_id" in found:
            raise SystemExit(
                f"the `chat_project_id` of the task {task['id']} differs from its "
                f"entry `{entry.task_name}`. An update cannot change a task's "
                "project, so the task must be deleted on claude.ai and deployed again."
            )
        if found:
            call = update_call(entry, task, found)
            outcomes.append(Outcome(entry, "update", task, found, call))
        else:
            outcomes.append(Outcome(entry, "unchanged", task))
    return outcomes


def next_run(task: dict) -> str:
    """Return `next_run_at` in the time zone of the schedule of `task`."""
    value = task.get("next_run_at")
    if not value:
        return "none"
    schedule = task.get("cron_expression") or ""
    zone = "UTC"
    if schedule.startswith("CRON_TZ="):
        zone = schedule.split()[0].removeprefix("CRON_TZ=")
    moment = datetime.fromisoformat(value).astimezone(ZoneInfo(zone))
    return moment.strftime("%Y-%m-%d %H:%M %Z")


def prompt_diff(outcome: Outcome) -> str:
    stored = task_values(outcome.task)["prompt"] or ""
    lines = difflib.unified_diff(
        stored.splitlines(),
        outcome.entry.values["prompt"].splitlines(),
        fromfile=f"task {outcome.task['id']}",
        tofile=outcome.entry.prompt_path,
        lineterm="",
    )
    return "\n".join(lines) or "The prompts differ in their line endings only."


def write_calls(plan: list[Outcome], directory: str) -> None:
    """Write the call of each create or update to a file of `directory`, which
    must not exist, and set `call_file` of its outcome."""
    try:
        os.makedirs(directory)
    except FileExistsError as error:
        raise SystemExit(f"{directory} exists. Name a new directory.") from error
    for index, outcome in enumerate(plan, start=1):
        if outcome.call is None:
            continue
        outcome.call_file = f"{index}-{outcome.action}.json"
        path = os.path.join(directory, outcome.call_file)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(outcome.call, file, ensure_ascii=False, indent=2)
            file.write("\n")


def render(plan: list[Outcome]) -> str:
    lines = ["Entries"]
    for outcome in plan:
        parts = [outcome.entry.task_name, outcome.action]
        if outcome.task is not None:
            parts.append(outcome.task["id"])
        if outcome.differences:
            parts.append(", ".join(outcome.differences))
        if outcome.call_file:
            parts.append(outcome.call_file)
        lines.append("  " + "  ".join(parts))
    lines += ["", "Tasks"]
    for outcome in plan:
        task = outcome.task
        if task is None:
            continue
        mode = (task.get("derived_state") or {}).get("permission_mode", "absent")
        lines.append(
            f"  {task['name']}  next run {next_run(task)}  permission mode {mode}"
            f"  https://claude.ai/code/routines/{task['id']}"
        )
    for outcome in plan:
        if "prompt" in outcome.differences:
            lines += ["", f"Prompt of {outcome.entry.task_name}", prompt_diff(outcome)]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tasks", help="the JSON response of `list`")
    parser.add_argument("manifests", nargs="+", help="the manifest files")
    parser.add_argument("--bodies", help="a new directory for the calls")
    args = parser.parse_args(argv)
    plan = make_plan(args.manifests, load_tasks(args.tasks))
    if args.bodies:
        write_calls(plan, args.bodies)
    print(render(plan))


if __name__ == "__main__":
    main()
