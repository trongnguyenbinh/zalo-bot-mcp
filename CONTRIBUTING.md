<p align="center">English | <a href="CONTRIBUTING.vi.md">Tiếng Việt</a></p>

# Contributing

Thanks for looking. This project is one person's side project, so this document is short on
ceremony and specific about the two things that actually matter here: the access gate, and
not leaking bot tokens.

## Before you start

- Contributions are licensed under the [MIT License](LICENSE), same as the rest of the
  project. There is no CLA and no sign-off requirement.
- **Found a security problem? Do not open an issue or a PR.** Use private reporting, see
  [SECURITY.md](SECURITY.md). A public PR that fixes a gate bypass also publishes the
  bypass, and every running install is exposed until people upgrade.
- **Never paste a bot token, a real chat ID, or raw unredacted logs** into an issue, a PR,
  a test fixture, or a screenshot. Bot tokens appear in poller logs. Scrub before posting.
- Be decent to people. There is no formal code of conduct because I cannot staff an
  enforcement process. I will block anyone who makes this unpleasant, and that is the whole
  policy.
- New to the project? Read [docs/getting-started.md](docs/getting-started.md) first
  (bản tiếng Việt: [docs/getting-started.vi.md](docs/getting-started.vi.md)). It is faster
  than reading the source.

## Development setup

Python 3.10 or newer. No database, no Docker, no services to start.

```bash
git clone https://github.com/trongnguyenbinh/zalo-bot-mcp.git
cd zalo-bot-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the checks:

```bash
ruff check .
pytest -q
```

The suite is 144 tests and finishes in under a second. It needs no network, no token, and
no Zalo account: the API client is exercised against fakes. If a test of yours needs a live
bot to pass, it belongs in a manual note in the PR description, not in `tests/`.

CI runs exactly these two commands on Python 3.10 and 3.14
(see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Green locally means green on CI.

One thing to know: **`ruff format` is not enforced yet.** Three existing files are not
formatted, and reformatting them inside an unrelated PR turns a five-line change into an
unreviewable diff. Match the style of the code around you, run `ruff check .`, and leave
`ruff format` alone unless the PR is explicitly about formatting.

## Workflow

1. **Open an issue first for anything non-trivial.** A bug fix, a typo, a doc correction, a
   test: send the PR directly. A new tool, a new config key, a change to how access is
   decided: talk to me first. I would rather say "not this way" in a comment than on a
   branch you spent a weekend on.
2. **Branch from `main`.** Short descriptive name, `fix/dedupe-on-restart` style. You will
   be working from a fork; `main` here rejects direct pushes and force-pushes.
3. **One logical change per PR.** Two unrelated fixes are two PRs. It is not bureaucracy, it
   is that I review these in the evening and a focused diff is the difference between merged
   tonight and merged in three weeks.
4. **Tests come with the change.** New behaviour needs a test. A bug fix needs a test that
   fails before your fix and passes after. This is the one rule I do not bend, because the
   suite is the only thing standing between a refactor and a bot that silently stops
   answering.
5. **Run `ruff check .` and `pytest -q` before pushing.**
6. **Open the PR against `main`** and describe what breaks if the change is wrong. CI has to
   be green before I merge.

## Changes that touch the gate

`src/zalo_bot_mcp/gate.py` and `src/zalo_bot_mcp/access.py` decide whose messages reach a
session that can read files and run commands on someone's machine. A mistake there is not a
bug, it is an unlocked door on every install.

If your PR touches either file, or the access config format:

- **Say so in the PR title or the first line of the description.** I want to know before I
  start reading.
- **Include a test for the deny path, not just the allow path.** "The allowed user gets
  through" is the easy half. The test that matters is "the unapproved user still does not,
  after this change".
- **Do not widen a default.** If a change makes something reachable that was not reachable
  before, that is a design decision, and it needs an issue first, not a PR.
- **Expect a slow review.** I will read these line by line and I will ask questions that
  sound pedantic. Nothing personal, this is the part of the codebase where being wrong is
  expensive for people who are not in this conversation.

The threat model, and what counts as a vulnerability versus intended design, is written out
in [SECURITY.md](SECURITY.md#what-counts). Read it before proposing changes here.

## Commit messages and PR titles

Commits use the `type: short summary` shape, imperative mood:

```
fix: drop duplicate updates after a poller restart
docs: document the group mention requirement
```

Types in use: `feat`, `fix`, `docs`, `test`, `refactor`, `ci`, `chore`.

**This is a convention, not a check.** Nothing in CI parses your commit messages and no
tooling computes a version number from them, so a PR will never be rejected over a subject
line. Follow it because it keeps the log readable.

**PR titles are different, and do get read by a machine.** GitHub releases are generated
from merged PR titles, so your title ends up verbatim in the public release notes. Write it
as the changelog line you would want to read: what changed, not what you did.

## Scope

This server does one thing: bridge the Zalo Bot API into an MCP session, with a gate in
front of it.

Outside the scope, and I will close these with a link back here:

- **Other chat platforms.** Telegram, Discord, Messenger. This is a Zalo server. The
  abstraction that would make it generic is exactly the abstraction that makes the gate hard
  to audit.
- **Webhook mode.** Long polling is the design, not a limitation to route around: no public
  URL, no tunnel, no inbound port, runs on a laptop behind NAT.
- **Anything letting a Zalo message change access config.** Not a missing feature. Access is
  granted from the operator's terminal and nowhere else, and that is load-bearing.
- **Hosting, multi-tenancy, a web dashboard, a plugin system.**

Behaviour that Zalo's own API imposes (2000-character messages, mention-gated groups, no
message editing, no reactions, no offset cursor) is not something a PR here can fix. The
current list is in the README.

Nothing personal in a close. The MIT license means a fork is a completely reasonable answer,
and if you build one I will link to it from the README.

## What to expect from me

I maintain this alone, around a full-time job. So, honestly:

- **I read every issue and PR.** Usually within a week. Sometimes not.
- **I do not promise a review deadline.** A promise of 24 hours I miss is worse for you than
  no promise at all, because you sit there refreshing instead of getting on with your week.
- **Security reports jump the queue**, on the timeline in [SECURITY.md](SECURITY.md)
  (acknowledged within 7 days).
- **Small, tested, focused PRs get merged fastest**, by a wide margin. A 20-line fix with a
  regression test is a ten-minute review. A 400-line refactor with no tests may sit for a
  month and then get closed, which wastes your time more than mine.
- **If a PR has gone quiet for two weeks, ping it.** I am not ignoring you, it fell off the
  page. A nudge is welcome, not rude.
- **This is version 0.x.** Tool names, config file shapes, and CLI flags can change between
  minor versions. If you are building on top of this, pin the version.

## Questions

Questions, ideas, and "is this supposed to work like that?" go to
[Discussions](https://github.com/trongnguyenbinh/zalo-bot-mcp/discussions). Issues are for
things that are broken, so a question filed there just gets moved.

Check [docs/getting-started.md](docs/getting-started.md) first: setup problems are almost
always a missing channel flag or a bot that was never mentioned in the group.
