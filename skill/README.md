# The operating skill

Three commands that let a coding-agent session run GPT Web Call without being
handed the 561-line protocol first.

| command | what it does |
|---|---|
| `/webcall:init` | installs the system from scratch, or rechecks an existing install, and finishes with a live smoke test it invents on the spot |
| `/webcall:prep` | prepares one bounded call: unbiased request, explicit file list, unique routing names, pre-send check |
| `/webcall:menu` | everything else — status, health, finish, recover, repair, stop, delete, manual fallback, watch, local responder |

Nothing here fires on its own. All three carry
`disable-model-invocation: true`, because they install software, register a
native-messaging host, and spend live model interactions.

## Install for Claude Code

The plugin ships inside this repository, so there is nothing to reconstruct:

```powershell
claude --plugin-dir "<path-to-this-repo>\skill\webcall"
```

Then `/webcall:init`, `/webcall:prep`, `/webcall:menu`.

To load it in every session instead, add the same directory as a local plugin
through `/plugin`.

## Codex and other hosts

`webcall/skills/<name>/SKILL.md` are plain Agent Skills — frontmatter plus a
markdown body — so any host that loads skill folders can use them unchanged.

Codex has no verified `/plugin:skill` spelling, so the exact three names above
are guaranteed on Claude Code only. `webcall/adapters/codex/AGENTS.md` exposes
the same three workflows as instructions.

## Layout

```
skill/
  README.md                        this file
  webcall/
    .claude-plugin/plugin.json     namespace: webcall
    references/OPERATING_CORE.md   read once per session, by all three
    references/SMOKE_TEST.md       read only when a smoke test is due
    skills/init/SKILL.md
    skills/prep/SKILL.md
    skills/menu/SKILL.md
    adapters/codex/AGENTS.md
```

`OPERATING_CORE.md` holds what a session must know before its first action.
Everything rarer stays in `WEB_CALL_PROTOCOL.md` at the repository root, which
remains the full contract and the thing the skills point at.
