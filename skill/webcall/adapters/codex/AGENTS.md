# GPT Web Call on Codex and other hosts

**Install the three skills. Do not paste their contents into a session.**

`../../skills/init/`, `../../skills/prep/` and `../../skills/menu/` are Agent
Skills: a folder, a `SKILL.md`, YAML frontmatter naming the skill, a markdown
body. That format is host-neutral, so any host that loads skill folders loads
these unchanged, and the workflow text stays in one place instead of drifting
per host.

`../../references/` holds what all three read — `OPERATING_CORE.md` before any
action, `SMOKE_TEST.md` only when a smoke test is due. Keep it beside `skills/`;
the bodies link to it as `../../references/`.

## Installing

Claude Code has a plugin manifest here already, so `python
scripts/install_skill.py` at the repository root does it.

For Codex, and for any other host, install these three folders the way that host
installs skills, then invoke them explicitly by name. **We have not verified the
exact command on any host but Claude Code** — check your host's own skills
documentation rather than trusting a command written here.

Whatever the host, invocation must stay explicit. All three carry
`disable-model-invocation: true` in their frontmatter, and a host that ignores
that field should be configured to require explicit invocation some other way:
these skills install software, register a native-messaging host, and spend live
model interactions.

## What does not change on any host

- The operator clicks Go, Attach, Send, every download, and Done. Never automate
  around that.
- Nothing under `calls/` or `state/` is ever published, uploaded, or quoted.
- Downloads are attributed by filename alone, so no two live calls may expect
  the same name.
- The skills are the way in. `WEB_CALL_PROTOCOL.md` is the reference they cite,
  not a second entry point — if something is missing from a skill, add it there.
