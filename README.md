<p align="center">English | <a href="README.vi.md">Tiếng Việt</a></p>

<h1 align="center">zalo-bot-mcp</h1>

<p align="center">
  Talk to your AI agent from a Zalo group.
</p>

<p align="center">
  <a href="https://pypi.org/project/zalo-bot-mcp/"><img src="https://img.shields.io/pypi/v/zalo-bot-mcp.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/zalo-bot-mcp/"><img src="https://img.shields.io/pypi/pyversions/zalo-bot-mcp.svg" alt="Python versions"></a>
  <a href="#license"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/status-early%20development-orange.svg" alt="Early development">
</p>

An MCP channel server for the [Zalo Bot API](https://bot.zapps.me/docs/). Messages sent to
your Zalo bot arrive in an MCP client session; the session replies through a tool call.

> **Early.** The server is on PyPI and has been exercised against a real bot, but the MCP
> channel it targets is still an experimental Claude Code capability.

## How it works

```
Zalo group  ──mention──▶  getUpdates  ──▶  gate  ──▶  MCP session
                                            │              │
                                       (not allowed)    reply tool
                                            │              │
                                          dropped  ◀───────┘
                                                      sendMessage
```

The server polls Zalo with `getUpdates`, so it needs no public URL, no webhook endpoint,
and no tunnel. It runs on a laptop behind NAT.

Every inbound message passes the gate before anything else sees it. The gate is the only
door.

## Access control

**Direct messages** follow one of three policies:

| Policy | Unknown sender gets |
| --- | --- |
| `pairing` | A short-lived code you approve out of band |
| `allowlist` | Nothing. The message is dropped silently |
| `disabled` | Nothing. All DMs are dropped |

**Groups** must be configured by ID. Adding the bot to a group does not enable it. You can
also restrict which members are allowed to trigger it.

Two rules the code enforces:

1. No Zalo message can change the access config. A message asking to be added to the
   allowlist is exactly what an injection attack looks like, so approvals happen outside
   the channel.
2. The server refuses to start if the allowlist contains a wildcard. It is easy to widen an
   allowlist during testing and forget to narrow it again.

Being on the allowlist means you can talk to the bot. It does not grant authority to act on
anything.

## Zalo platform constraints

These come from the Zalo Bot API itself, and they shape what any Zalo bot can do. Zalo owns
these rules and changes them without notice, so treat <https://bot.zapps.me/> as the source
of truth and this section as a summary that may be out of date:

- **Groups are mention-gated.** A bot receives a group message only when it is mentioned or
  when someone replies to one of its messages. It cannot watch a conversation passively.
- **Messages cap at 2000 characters.** Longer replies get split across several messages.
- **No offset cursor.** `getUpdates` takes only `timeout`, so deduplication happens by
  `message_id` rather than by advancing a cursor.
- **No message editing.** Replies cannot be updated in place, so progress on a long task
  arrives as new messages.
- **No reactions.** The API has no reaction endpoint, so a bot cannot acknowledge a message
  with an emoji. It can send a typing indicator (`sendChatAction`) and stickers.
- **Free-plan quotas.** Zalo's Basic (free) plan allows 3 bots per account, 50 users per bot,
  3 group chats (marked beta), and 3,000 outbound messages per month. A paid Pro plan exists.
  Current plans and quotas: <https://bot.zapps.me/>.

## Install

Two ways in, both need [uv](https://docs.astral.sh/uv/): as a **Claude Code
plugin** (`/plugin marketplace add trongnguyenbinh/zalo-bot-mcp`, then
`/plugin install zalo@zalo-bot-mcp`), or as a **Python package** registered in
your `.mcp.json`. Either way, Claude Code must then be started with the
channel flag or messages never reach the session.

The full walkthrough, from creating the bot on Zalo to the first replied
message, plus all `/zalo:*` skills and the `zalo-bot-mcp-admin` CLI, lives in
**[docs/getting-started.md](docs/getting-started.md)**
(bản tiếng Việt: [docs/getting-started.vi.md](docs/getting-started.vi.md)).

## Development

```bash
git clone https://github.com/trongnguyenbinh/zalo-bot-mcp.git
cd zalo-bot-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Runtime dependencies are `httpx` and `mcp`. Nothing else. The Zalo endpoints are called
directly, so the whole API surface stays readable in one file.

## Not affiliated with Zalo

This is a personal, unofficial project. It is not built, endorsed, reviewed, or supported by
Zalo, VNG Corporation, or any of their affiliates. "Zalo" is their trademark, used here only
to say which service this talks to.

It calls the public [Zalo Bot API](https://bot.zapps.me/docs/) the same way any third-party
bot does. Your bot, your token, your account, your responsibility: read Zalo's own terms
before pointing this at anything that matters, and expect the API to change without warning.

It is published under the MIT license, which means it comes with no warranty and no
liability. If something breaks in your setup, you own the breakage.

## License

MIT
