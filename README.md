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

> **Early.** The server runs and has been exercised against a real bot, but it is not on
> PyPI yet and the MCP channel it targets is an experimental Claude Code capability.

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

Both paths need [uv](https://docs.astral.sh/uv/) on the machine.

### As a Claude Code plugin

```
/plugin marketplace add trongnguyenbinh/zalo-bot-mcp
/plugin install zalo@zalo-bot-mcp
```

The plugin starts the server for you and adds the `/zalo:*` skills: `set-token`,
`pending-chats`, `approve`, `allow`, `revoke`, `list`, `group-add`, `group-remove`.
Start with `/zalo:set-token` to install your bot token from the clipboard.

### As a Python package

Not on PyPI yet. Until then, install from source:

```bash
uv tool install git+https://github.com/trongnguyenbinh/zalo-bot-mcp
```

Then register the server in your project's `.mcp.json`:

```json
{ "mcpServers": { "zalo": { "command": "zalo-bot-mcp" } } }
```

The `zalo-bot-mcp-admin` CLI manages tokens and access from the terminal.

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
