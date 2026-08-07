<h1 align="center">zalo-bot-mcp</h1>

<p align="center">
  Talk to your AI agent from a Zalo group.
</p>

<p align="center">
  <a href="#license"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/status-early%20development-orange.svg" alt="Early development">
</p>

An MCP channel server for the [Zalo Bot API](https://bot.zapps.me/docs/). Messages sent to
your Zalo bot arrive in an MCP client session; the session replies through a tool call.

> **Not usable yet.** The design is settled and the packaging is in place. The code is not
> written. Watch the repo if you want to know when it runs.

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

These come from the Zalo Bot API itself, and they shape what any Zalo bot can do:

- **Groups are mention-gated.** A bot receives a group message only when it is mentioned or
  when someone replies to one of its messages. It cannot watch a conversation passively.
- **Messages cap at 2000 characters.** Longer replies get split across several messages.
- **No offset cursor.** `getUpdates` takes only `timeout`, so deduplication happens by
  `message_id` rather than by advancing a cursor.
- **No message editing.** Replies cannot be updated in place, so progress on a long task
  arrives as new messages.
- **Beta limits.** One bot joins at most 3 groups, each capped at 50 members.

## Install

Not published yet.

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

## License

MIT
