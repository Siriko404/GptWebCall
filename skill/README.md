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

The plugin ships inside this repository as its own local marketplace, so there
is nothing to build or copy. Inside Claude Code:

```text
/plugin marketplace add <path-to-this-repo>\skill\webcall
/plugin install webcall@webcall-local
```

**Then restart Claude Code.** Commands are registered at startup; they will not
appear in the session that installed them.

After the restart, `/webcall:` autocompletes to `init`, `prep`, and `menu`.

To try it for one session without installing:

```powershell
claude --plugin-dir "<path-to-this-repo>\skill\webcall"
```

## Codex and other hosts

`webcall/skills/<name>/SKILL.md` are plain Agent Skills — frontmatter plus a
markdown body — so any host that loads skill folders can use them unchanged.

Codex has no verified `/plugin:skill` spelling, so the exact three names above
are guaranteed on Claude Code only. `webcall/adapters/codex/AGENTS.md` exposes
the same three workflows as instructions.

## Layout

```
skill/
  README.md                          this file
  webcall/
    .claude-plugin/plugin.json       namespace: webcall
    .claude-plugin/marketplace.json  lets this directory install itself
    commands/{init,prep,menu}.md     the three slash commands
    skills/{init,prep,menu}/SKILL.md the workflow each command follows
    references/OPERATING_CORE.md     read once per session, by all three
    references/SMOKE_TEST.md         read only when a smoke test is due
    adapters/codex/AGENTS.md
```

The commands are thin: each reads the operating core, then follows its skill.
The skill bodies hold the actual workflow, so the two hosts share one text.

`OPERATING_CORE.md` holds what a session must know before its first action.
Everything rarer stays in `WEB_CALL_PROTOCOL.md` at the repository root, which
remains the full contract and the thing the skills point at.
