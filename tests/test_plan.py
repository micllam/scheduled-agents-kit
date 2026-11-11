import contextlib
import io
import json
import os
import tempfile
import unittest

from tests import plan

MANIFEST = """\
namespace = "example"

[[task]]
name = "test coverage"
schedule = "CRON_TZ=Europe/London 0 2 * * 6"
model = "claude-opus-5-5"
prompt = "prompts/test-coverage.md"
repositories = ["https://github.com/example-org/example"]
environment_id = "env_example"
enabled = true
effort = "high"
"""

PROMPT = "Review the coverage.\n\tIndented, with “quotes” and 日本語.\n"


def task(**changes):
    """Return a task of `list` that matches the entry of `MANIFEST`."""
    record = {
        "id": "trig_example",
        "name": "example: test coverage",
        "cron_expression": "CRON_TZ=Europe/London 0 2 * * 6",
        "enabled": True,
        "next_run_at": "2026-11-14T02:00:00Z",
        "mcp_connections": [],
        "derived_state": {
            "model": "claude-opus-5-5",
            "prompt": PROMPT.removesuffix("\n"),
            "permission_mode": "auto",
        },
        "job_config": {
            "ccr": {
                "environment_id": "env_example",
                "session_context": {
                    "model": "claude-opus-5-5",
                    "effort_level": "high",
                    "sources": [
                        {
                            "git_repository": {
                                "url": "https://github.com/example-org/example"
                            }
                        }
                    ],
                },
            }
        },
    }
    record.update(changes)
    return record


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.manifest = os.path.join(self.tmp.name, "manifest.toml")
        self.write("manifest.toml", MANIFEST)
        self.write("prompts/test-coverage.md", PROMPT)

    def write(self, path, text):
        full = os.path.join(self.tmp.name, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as file:
            file.write(text)
        return full

    def make_plan(self, tasks, paths=None):
        return plan.make_plan(paths or [self.manifest], tasks)

    def test_matching_task_is_unchanged(self):
        outcome = self.make_plan([task()])[0]
        self.assertEqual((outcome.action, outcome.differences), ("unchanged", []))

    def test_stop_conditions(self):
        manifests = {
            "missing field": (
                MANIFEST.replace('model = "claude-opus-5-5"\n', ""),
                "missing fields",
            ),
            "unknown field": (MANIFEST + 'branch = "main"\n', "unknown fields"),
            "no namespace": (
                MANIFEST.replace('namespace = "example"\n', ""),
                "must contain `namespace`",
            ),
            "wrong type": (
                MANIFEST.replace("enabled = true", 'enabled = "true"'),
                "`enabled` must be a bool",
            ),
            "absent prompt": (
                MANIFEST.replace("test-coverage.md", "absent.md"),
                "absent.md",
            ),
            "duplicate name": (
                MANIFEST + MANIFEST.removeprefix('namespace = "example"\n'),
                "two entries name the task",
            ),
            "invalid TOML": (MANIFEST + "[[task]\n", "invalid TOML"),
            "repository not a string": (
                MANIFEST.replace('["https://github.com/example-org/example"]', "[1]"),
                "must be a list of strings",
            ),
            "unknown top-level key": (
                "version = 1\n" + MANIFEST,
                "must contain `namespace`",
            ),
            "task not a list": (
                'namespace = "example"\ntask = "x"\n',
                "must contain `namespace`",
            ),
            "entry not a table": (
                'namespace = "example"\ntask = ["x"]\n',
                "must be a table",
            ),
        }
        for label, (manifest, fragment) in manifests.items():
            with self.subTest(label):
                self.write("manifest.toml", manifest)
                with self.assertRaisesRegex(SystemExit, fragment):
                    self.make_plan([])
        self.write("manifest.toml", MANIFEST)
        with (
            self.subTest("absent manifest"),
            self.assertRaisesRegex(SystemExit, "other.toml"),
        ):
            self.make_plan([], [os.path.join(self.tmp.name, "other.toml")])
        with (
            self.subTest("two tasks with the name"),
            self.assertRaisesRegex(SystemExit, "share the name"),
        ):
            self.make_plan([task(), task(id="trig_other")])
        listings = {
            "invalid JSON": ("{", "must contain the JSON response"),
            "no data": ("{}", "must contain the list `data`"),
            "has_more": (json.dumps({"data": [], "has_more": True}), "has_more"),
        }
        for label, (text, fragment) in listings.items():
            with (
                self.subTest(label),
                self.assertRaisesRegex(SystemExit, fragment),
            ):
                plan.load_tasks(self.write("list.json", text))

    def test_entry_without_task_is_created(self):
        call = self.make_plan([])[0].call
        self.assertEqual(call["action"], "create")
        body = call["body"]
        self.assertEqual(body["name"], "example: test coverage")
        self.assertIs(body["clear_mcp_connections"], True)
        ccr = body["job_config"]["ccr"]
        self.assertEqual(
            ccr["events"][0]["data"]["message"]["content"], PROMPT.removesuffix("\n")
        )
        self.assertEqual(ccr["session_context"]["effort_level"], "high")

    def test_update_contains_the_differing_fields(self):
        def ccr(record):
            return record["job_config"]["ccr"]

        cases = {
            "schedule": (
                lambda t: t.update(cron_expression="0 2 * * 6"),
                {"cron_expression"},
            ),
            "enabled": (lambda t: t.update(enabled=False), {"enabled"}),
            "connectors": (
                lambda t: t.update(mcp_connections=[{"name": "x"}]),
                {"clear_mcp_connections"},
            ),
            "model": (
                lambda t: t["derived_state"].update(model="other"),
                {"job_config"},
            ),
            "prompt": (
                lambda t: t["derived_state"].update(prompt="old"),
                {"job_config"},
            ),
            "repositories": (
                lambda t: ccr(t)["session_context"].update(sources=[]),
                {"job_config"},
            ),
            "environment": (
                lambda t: ccr(t).update(environment_id="env_other"),
                {"job_config"},
            ),
        }
        for label, (change, keys) in cases.items():
            with self.subTest(label):
                record = task()
                change(record)
                call = self.make_plan([record])[0].call
                self.assertEqual(
                    (call["action"], call["trigger_id"]), ("update", "trig_example")
                )
                self.assertEqual(set(call["body"]), keys)

    def test_entry_without_effort_omits_effort_level(self):
        self.write("manifest.toml", MANIFEST.replace('effort = "high"\n', ""))
        outcome = self.make_plan([task()])[0]
        self.assertEqual(outcome.differences, ["effort"])
        context = outcome.call["body"]["job_config"]["ccr"]["session_context"]
        self.assertNotIn("effort_level", context)

    def test_next_run_is_in_the_zone_of_the_schedule(self):
        cases = {
            "CRON_TZ": (task(), "2026-11-14 02:00 GMT"),
            "no prefix": (task(cron_expression="0 2 * * 6"), "2026-11-14 02:00 UTC"),
            "no next run": (task(next_run_at=None), "none"),
        }
        for label, (record, expected) in cases.items():
            with self.subTest(label):
                self.assertEqual(plan.next_run(record), expected)

    def test_render_shows_the_prompt_diff(self):
        stored = PROMPT.removesuffix("\n")
        cases = {
            "text": ({"prompt": "old"}, ["-old", "+Review the coverage."]),
            "line endings": (
                {"prompt": stored.replace("\n", "\r\n")},
                ["differ in their line endings only"],
            ),
            "no derived state": (None, ["+Review the coverage."]),
        }
        for label, (derived, expected) in cases.items():
            with self.subTest(label):
                output = plan.render(self.make_plan([task(derived_state=derived)]))
                self.assertIn("Prompt of example: test coverage", output)
                for text in expected:
                    self.assertIn(text, output)

    def test_main_writes_a_call_per_create_or_update(self):
        listing = self.write("list.json", json.dumps({"data": [task(enabled=False)]}))
        bodies = os.path.join(self.tmp.name, "bodies")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            plan.main([listing, self.manifest, "--bodies", bodies])
        self.assertEqual(os.listdir(bodies), ["1-update.json"])
        self.assertIn("1-update.json", out.getvalue())
        self.assertIn(
            "permission mode auto  https://claude.ai/code/routines/trig_example",
            out.getvalue(),
        )
        with self.assertRaises(SystemExit):
            plan.main([listing, self.manifest, "--bodies", bodies])


if __name__ == "__main__":
    unittest.main()
