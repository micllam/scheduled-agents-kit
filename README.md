# scheduled-agents-kit

A kit to deploy the [scheduled tasks](https://code.claude.com/docs/en/routines)
of claude.ai.

A manifest is a TOML file that defines one or more scheduled tasks, in the
format of [`docs/manifest.md`](docs/manifest.md).

The Claude Code skill `deploy-scheduled-tasks` reads manifests from disk and
creates or updates their tasks in the session's claude.ai account. The skill can
be installed from `skills/deploy-scheduled-tasks/`, and it requires Python 3.11
or later.

> [!WARNING]
> The skill manages the tasks through the `RemoteTrigger` tool of Claude Code,
> which calls an undocumented API of claude.ai. A change of that API can break
> the skill without notice.

## Example

The manifest [`examples/test-coverage.toml`](examples/test-coverage.toml)
defines a task that runs every Saturday at 02:00, London time:

```toml
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
```

The prompt of the task is the text of
[`examples/prompts/test-coverage.md`](examples/prompts/test-coverage.md).

## Deployment

In a Claude Code session, run the skill with the paths of one or more manifests,
such as the path of the example:

```
/deploy-scheduled-tasks examples/test-coverage.toml
```

A deployment of the example requires an `environment_id` of the claude.ai
account and a repository that the connected GitHub account can read.

The skill then runs these steps:

1. It looks up the task of each manifest entry in claude.ai by name and compares
   the entry with that task. For an entry without a matching task, it plans a
   new task. It stops without changing any task when the manifests are invalid
   or when two tasks on claude.ai have the name of an entry.
2. It shows the pending action for each entry and the prompt diffs. When an
   action is pending, it asks the user for approval.
3. After the approval, it creates and updates the tasks. It then checks that the
   deployed tasks match the manifests, and its final message lists the URL of
   each task on claude.ai.

**Manifest only.** A change to a deployed task should be made in its manifest
and then deployed with the skill. The next deployment reverts a change made in
the web form to a field of the manifest, after it shows the difference for
approval.

## Limitations

The skill has these known limitations:

- It deploys each task without
  [connectors](https://code.claude.com/docs/en/routines#connectors).
- It deploys each task outside the projects of claude.ai, so a run cannot read a
  project's documents.
- It cannot delete a task. When an entry is removed from its manifest or
  renamed, its task stays on claude.ai and keeps its schedule.

## License

scheduled-agents-kit is released under the [MIT License](LICENSE).
