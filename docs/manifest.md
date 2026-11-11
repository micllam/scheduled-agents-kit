# Manifest format

A manifest is a TOML file with the key `project` and a `[[task]]` table per
task:

```toml
project = "example"

[[task]]
name = "test coverage"
schedule = "CRON_TZ=Europe/London 0 2 * * 6"
model = "claude-opus-5-5"
prompt = "prompts/test-coverage.md"
repositories = ["https://github.com/example-org/example"]
environment_id = "env_example"
enabled = true
effort = "high"
```

On claude.ai each task appears as `<project>: <name>`, as in
`example: test coverage`.

Each field of a task is required except `effort`, and a task without `effort`
runs at the default effort level of the model.

| Field | Type | Contents |
|---|---|---|
| `name` | string | The name of the task, which must be unique within its `project`. |
| `schedule` | string | A cron expression of five fields, with an optional `CRON_TZ=<zone>` prefix. Without the prefix the expression is in UTC. |
| `model` | string | The model id of a run, such as `claude-opus-5-5`. |
| `prompt` | string | The path of the prompt file, relative to the manifest. A deployment sends the text of the file as the prompt of the task. |
| `repositories` | list of strings | The URLs of the GitHub repositories that a run clones. A task with a repository requires a GitHub account that is connected to the claude.ai account and can read the repository. Its creation fails without the connection. |
| `environment_id` | string | The id of the claude.ai environment of a run. The `/schedule` command of Claude Code lists the environments with their ids. |
| `enabled` | boolean | Whether the task is enabled. |
| `effort` | string | The effort level of a run, such as `high`. |

The skill checks the manifests passed on its command line before it changes any
task. It aborts the deployment without making any changes when it finds:

- A missing field.
- An unknown field.
- A value of the wrong type.
- Two entries with the same task name.
- Two tasks on claude.ai with the task name of an entry.
