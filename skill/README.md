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

## Install

The plugin ships inside this repository as its own local marketplace, so there
is nothing to build or copy. From the repository root:

```powershell
python scripts/install_skill.py
```

**Then restart Claude Code.** Commands register at startup; they do not appear
in the session that installed them. After the restart, `/webcall:` autocompletes
to `init`, `prep`, and `menu`.

The script writes two keys into `~/.claude/settings.json` and nothing else — the
same two that `/plugin marketplace add` and `/plugin install` write:

```json
"extraKnownMarketplaces": { "webcall-local": { "source": { "source": "directory", "path": "…/skill/webcall" } } },
"enabledPlugins":         { "webcall@webcall-local": true }
```

It backs the file up first, preserves everything else, and does nothing when
both keys are already correct. `--dry-run` shows the change without making it.

**If the commands are still missing after a restart**, type these two lines and
restart again:

```text
/plugin marketplace add <path-to-this-repo>\skill\webcall
/plugin install webcall@webcall-local
```

To try it for one session without registering anything:

```powershell
claude --plugin-dir "<path-to-this-repo>\skill\webcall"
```

## Codex and other hosts

`webcall/skills/<name>/` are plain Agent Skills — a folder, a `SKILL.md`,
frontmatter plus a markdown body — so any host that loads skill folders loads
these unchanged. Install them as skills there too; do not paste their contents
into a session, which puts a second entry point beside the skills and is what
this replaced.

The exact install command is verified on Claude Code only.
`webcall/adapters/codex/AGENTS.md` says what a host has to provide and what must
stay true wherever they run.

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
