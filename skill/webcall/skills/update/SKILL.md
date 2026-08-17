---
name: update
description: Update this GPT Web Call installation to the latest published version — fast-forward the checkout, re-register the native host and skills, and name the two steps only a human can do. Use only when the user explicitly invokes this workflow.
disable-model-invocation: true
---

# `/webcall:update`

Read [OPERATING_CORE](../../references/OPERATING_CORE.md) first.

Updating replaces the code that is watching a running call's downloads. Do not
improvise this; run the script, which refuses when it must.

## 1. Run it

```powershell
python <root>\scripts\update.py
```

It prints one JSON object and exits `0` on success, `2` on a refusal. It
fast-forwards to the newest published release tag, or to `origin/main` when the
repository has never published one.

**Never work around a refusal.** Do not pass force flags, do not stash, do not
merge or rebase by hand, and do not delete `state/active/` to get past the
running-call check. Each refusal names a thing the operator has to decide.

| refusal | what it means | what to do |
|---|---|---|
| calls still running | the download monitor is in the code being replaced | finish or stop them, then update |
| uncommitted changes | local work would be at risk | show the operator the listed files and ask; commit or stash is their call |
| diverged | this checkout and the published version each have commits the other lacks | stop. Reconciling is the operator's decision, not yours |
| no remote named origin | this is not a checkout of the published repository | stop and say so |

## 2. Read the result

`ALREADY_CURRENT` means nothing to do. `commits_ahead` above zero is normal on
the machine the system is developed on — say "already current" and stop. Do not
run step 3.

`UPDATED` reports how many commits landed, which surfaces moved, and
`next_steps`.

## 3. Re-register

```powershell
python <root>\scripts\setup.py
```

Safe to run again; it undoes nothing already installed. It re-registers the
native host, which matters when the host manifest moved. When Chrome already has
this extension loaded it says so and returns rather than waiting.

It will report the skills as already registered, and that is correct:
`install_skill.py` points Claude Code at this checkout rather than copying it,
so the fast-forward already updated them on disk.

## 4. Hand back the human steps

Print `next_steps` verbatim. Two of them cannot be done by any script, and an
update that stays silent about them leaves the operator running old code while
believing they are current:

- **The extension needs reloading** in `chrome://extensions`. Chrome removed
  `--load-extension` from stable; nothing can script this.
- **Claude Code needs restarting** when `skill/` moved. The new files are
  already on disk — Claude Code reads them from this checkout — but plugins
  register at startup, so what is running in this session is still the old
  version, including this skill.

Then say plainly that the update has not been proven, only installed. Offer
`/webcall:init`, which rechecks the install and finishes with a live smoke test.

## Always refuse

- Updating while any call is active, by any route.
- Discarding, stashing, or committing the operator's uncommitted work for them.
- Resolving a divergence — merging, rebasing, resetting, or force-pulling.
- Reporting success on the strength of a fast-forward alone. The checkout moved;
  the install has not been rechecked and the extension has not been reloaded.
- Pulling from any remote the operator did not install from.

## Proof it worked

`update.py` returns `UPDATED` with the new HEAD, `setup.py` exits `0`, and the
operator confirms the extension reload. Until `/webcall:init` passes, the
correct claim is "updated, not yet verified".
