# Manifest format

A manifest is a TOML file with the string key `namespace` and a `[[task]]` table
per task. On claude.ai each task appears as `<namespace>: <name>`. A manifest
with any other key or field is invalid.

| Field | Type | Required | Contents |
|---|---|---|---|
| `name` | string | yes | The name of the task, which must be unique within its `namespace`. |
| `schedule` | string | yes | A cron expression of five fields, with an optional `CRON_TZ=<zone>` prefix. Without the prefix the expression is in UTC. |
| `model` | string | yes | The model id of a run, such as `claude-opus-5-5`. |
| `prompt` | string | yes | The path of the prompt file, relative to the manifest. A deployment sends the text of the file as the prompt of the task. |
| `repositories` | list of strings | yes | The URLs of the GitHub repositories that a run clones. A task with a repository requires a GitHub account that is connected to the claude.ai account and can read the repository. Its creation fails without the connection. |
| `environment_id` | string | yes | The id of the claude.ai environment of a run. The `/schedule` command of Claude Code lists the environments with their ids. |
| `enabled` | boolean | yes | Whether the task is enabled. |
| `effort` | string | no | The effort level of a run, such as `high`. Without the field, a run uses the default effort level of the model. |
| `chat_project_id` | string | no | The id of the claude.ai project of a run, such as `claude_proj_...`. A run can read and write the project's documents. Without the field, a task runs outside the projects of claude.ai. |
