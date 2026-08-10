# GPT Web Call — Codex adapter

Codex has no verified equivalent of Claude Code's `/plugin:skill` spelling, so
the three workflows are exposed here as plain instructions instead of commands.
The content is identical; only the entry point differs.

Point a Codex session at this file, or paste it into the project's own
`AGENTS.md`.

## The three workflows

Read `../../references/OPERATING_CORE.md` before any of them. It carries the
privacy boundary, how to find the installed root, the filename-routing rule, and
how to read a validation report.

| ask | do |
|---|---|
| install it, or check the install | follow `../../skills/init/SKILL.md` |
| prepare a call | follow `../../skills/prep/SKILL.md` |
| anything else | follow `../../skills/menu/SKILL.md` |

Each of those files opens with YAML frontmatter naming the workflow. Ignore the
frontmatter and follow the body.

## What does not change on any host

- The operator clicks Go, Attach, Send, every download, and Done. Never automate
  around that.
- Nothing under `calls/` or `state/` is ever published, uploaded, or quoted.
- Downloads are attributed by filename alone, so no two live calls may expect the
  same name.
- Never run these workflows without an explicit request. They install software,
  register a native-messaging host, and spend live model interactions.
