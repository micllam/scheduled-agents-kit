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

## Deployment

In a Claude Code session, run the skill with the paths of one or more manifests:

```
/deploy-scheduled-tasks <manifest-1> <manifest-2> ...
```

The skill then runs these steps:

1. It looks up the task of each manifest entry in claude.ai by name and compares
   the entry with that task. For an entry without a matching task, it plans a
   new task.
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
- It cannot delete a task. When an entry is removed from its manifest or
  renamed, its task stays on claude.ai and keeps its schedule.

## License

scheduled-agents-kit is released under the [MIT License](LICENSE).
