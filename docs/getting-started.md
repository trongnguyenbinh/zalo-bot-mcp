English | [Tiếng Việt](getting-started.vi.md)

# Getting started

Create a Zalo bot, then follow one of two install paths end to end. Each path
covers everything through your first delivered message, including the channel
flag — the step everyone misses.

## 1. Create your Zalo bot

Bots are created inside the Zalo app, through an official account called
**Zalo Bot Manager** (docs: <https://bot.zapps.me/docs/create-bot/>):

1. In the Zalo app, search for the OA **Zalo Bot Manager** and open the chat.
2. In the chat menu, choose **Tạo bot** (Create bot). This opens the
   **Zalo Bot Creator** mini app.
3. Name your bot. The name must start with the word `Bot`, for example
   `Bot MyShop`.
4. Confirm with **Tạo Bot**. The bot token arrives as a Zalo message to your
   own account. Treat it like a password: do not paste it into chats, files,
   or shell arguments. Step 2 below shows a safe way to install it.
5. On <https://bot.zapps.me/> pick a plan. The free **Basic** plan has a
   **Đăng ký gói** (subscribe) button; a paid Pro plan is listed as coming
   soon. Basic limits:

![Basic plan quotas](assets/quota-basic.png)

## 2. Install and run

There are two paths. **Pick one and follow it to the end** — each one below is
complete, from install to your first delivered message. They differ in more
than the install command, so do not mix steps between them.

| | Path A: plugin | Path B: Python package |
| --- | --- | --- |
| Install from | Claude Code | terminal |
| Access control via | `/zalo:*` skills | `zalo-bot-mcp-admin` CLI |
| Needs `.mcp.json` | no | yes, one per project directory |
| Channel entry | `plugin:zalo@zalo-bot-mcp` | `server:zalo` |
| Works from any directory | yes | only where `.mcp.json` lives |

Both need [uv](https://docs.astral.sh/uv/) installed. Both store state in
`~/.zalo-bot-mcp/`, so switching paths later keeps your token and allowlist.

---

### Path A: Claude Code plugin

**A1. Install the plugin.** Inside Claude Code:

```
/plugin marketplace add trongnguyenbinh/zalo-bot-mcp
/plugin install zalo@zalo-bot-mcp
```

This registers the MCP server and the `/zalo:*` skills.

**A2. Install the token.** Copy the bot token to your clipboard, then:

```
/zalo:set-token
```

It goes from the clipboard straight into `~/.zalo-bot-mcp/.env` with `0600`
permissions, never through the conversation transcript. That is why the skill
refuses to take the token as text — do not paste it into the chat.

**A3. Restart Claude Code with the channel flag.** In a terminal:

```bash
claude --dangerously-load-development-channels plugin:zalo@zalo-bot-mcp
```

Without this flag the server connects and the `reply` tool appears, but no
Zalo message ever reaches the session. See
[About that flag](#about-that-flag) for why it is named that.

**A4. Send the first message.** Message your bot on Zalo. You get a pairing
code back. Approve it in Claude Code:

```
/zalo:approve a1b2c3
```

Message again: it now arrives in the session.

**A5. Lock it down.** While the policy is `pairing`, any stranger who finds
your bot gets a pairing code. Once you are approved, close it:

```
/zalo:list
/zalo:policy allowlist
```

**To uninstall:** `/plugin uninstall zalo@zalo-bot-mcp`. That leaves
`~/.zalo-bot-mcp/` alone, so your token and allowlist survive. Delete that
directory too if you want a clean slate.

---

### Path B: Python package

**B1. Install.** In a terminal:

```bash
uv tool install zalo-bot-mcp
```

Or from source, for an unreleased commit:

```bash
uv tool install git+https://github.com/trongnguyenbinh/zalo-bot-mcp
```

**B2. Check your `PATH`.**

```bash
which zalo-bot-mcp
```

Nothing printed means `~/.local/bin` is not on your `PATH`. Run
`uv tool update-shell`, then open a new shell.

**B3. Create `.mcp.json`.** Installing the package does not create this file,
and Claude Code only looks for it in the directory you start it from. Create
it yourself, in the project directory you plan to work in:

```bash
cat > .mcp.json <<'EOF'
{ "mcpServers": { "zalo": { "command": "zalo-bot-mcp" } } }
EOF
```

**B4. Install the token.** On a terminal this prompts with the input hidden —
paste the token and press Enter:

```bash
zalo-bot-mcp-admin set-token
```

Piping works too (macOS shown; on Linux use `xclip -o -selection clipboard`
or `wl-paste` instead of `pbpaste`):

```bash
pbpaste | zalo-bot-mcp-admin set-token
```

Never pass the token as a command-line argument: it would land in your shell
history and be visible in the process list. The CLI verifies the token
against the live API (`getMe`) before writing anything and prints the bot name
on success. Setting `ZALO_BOT_TOKEN` in the environment also works.

**B5. Start Claude Code with the channel flag**, from the directory holding
your `.mcp.json`:

```bash
claude --dangerously-load-development-channels server:zalo
```

Without this flag the server connects and the `reply` tool appears, but no
Zalo message ever reaches the session. See
[About that flag](#about-that-flag) for why it is named that.

**B6. Send the first message.** Message your bot on Zalo. You get a pairing
code back. Approve it in the terminal:

```bash
zalo-bot-mcp-admin approve a1b2c3
```

Message again: it now arrives in the session.

**B7. Lock it down.** While the policy is `pairing`, any stranger who finds
your bot gets a pairing code. Once you are approved, close it:

```bash
zalo-bot-mcp-admin list               # confirm your id is in allowFrom
zalo-bot-mcp-admin policy allowlist
```

The command refuses to switch to `allowlist` while `allowFrom` is empty: that
combination locks out everyone including you, with no way left to request a
pairing code.

**To uninstall:**

```bash
uv tool uninstall zalo-bot-mcp
rm .mcp.json
```

That leaves `~/.zalo-bot-mcp/` alone, so your token and allowlist survive.
Delete that directory too if you want a clean slate.

---

### About that flag

MCP channels are an experimental Claude Code capability, off by default.

The flag is `--dangerously-load-development-channels`, not `--channels`. The
plain `--channels` flag only accepts plugins on an approved-channels allowlist
that ships inside Claude Code, and it rejects `server:` entries outright. zalo
is not on that allowlist, so the development flag is the only way to run it
today.

The prefix on the entry is required, and which prefix depends on your path.
Claude Code resolves `server:` names against the enterprise, user, project,
and local MCP scopes; a plugin registers its server outside all four, which is
why path A needs `plugin:` instead. A bare `zalo` resolves under neither.

Anthropic's guidance is that this flag is for developing your own channel
locally, not for running channels downloaded off the internet. This one was
downloaded off the internet. The mitigations are the gate and the rule that no
Zalo message can change who is allowed through — both readable in
[`src/zalo_bot_mcp/gate.py`](../src/zalo_bot_mcp/gate.py) and
[SECURITY.md](../SECURITY.md).

## 3. Commands

### `/zalo:*` skills (Claude Code)

| Skill | What it does |
| --- | --- |
| `/zalo:set-token` | Install the bot token from the clipboard. Example: copy token, then `/zalo:set-token` |
| `/zalo:list` | Show access state: DM policy, allowlist, groups, pending codes |
| `/zalo:policy` | Set the DM policy. Example: `/zalo:policy allowlist` |
| `/zalo:pending-chats` | Show chats the gate has blocked, with ready-to-run grant commands |
| `/zalo:approve` | Approve a pairing code. Example: `/zalo:approve a1b2c3` |
| `/zalo:allow` | Add a user_id to the allowlist directly. Example: `/zalo:allow 1234abcd` |
| `/zalo:revoke` | Remove a user_id from the allowlist. Example: `/zalo:revoke 1234abcd` |
| `/zalo:group-add` | Grant a group by chat_id. Example: `/zalo:group-add zgr-1a2b3c` |
| `/zalo:group-remove` | Revoke a group. Example: `/zalo:group-remove zgr-1a2b3c` |

Every grant skill refuses to run when the request came from a Zalo message
instead of you: that pattern is exactly what prompt injection looks like.

### `zalo-bot-mcp-admin` CLI (terminal)

The same operations without Claude Code. Same names, same behavior:

```bash
zalo-bot-mcp-admin list                      # show access state
zalo-bot-mcp-admin pending-chats             # blocked chats + suggested grants
zalo-bot-mcp-admin policy allowlist          # set DM policy
zalo-bot-mcp-admin approve a1b2c3            # approve a pairing code
zalo-bot-mcp-admin allow 1234abcd            # allowlist a user directly
zalo-bot-mcp-admin revoke 1234abcd           # remove a user
zalo-bot-mcp-admin group-add zgr-1a2b3c      # grant a group
zalo-bot-mcp-admin group-remove zgr-1a2b3c   # revoke a group
pbpaste | zalo-bot-mcp-admin set-token       # install token from clipboard
```

State lives in `~/.zalo-bot-mcp/` (override with `ZALO_MCP_STATE_DIR`).

## Troubleshooting

**The bot is completely silent.** Most likely a webhook is attached to the
bot: Zalo refuses `getUpdates` while one is set, and the server exits at boot
with the webhook URL in the error. Delete the webhook (`deleteWebhook` in the
Bot API) and start again.

**"another poller (pid N) holds the lock" at startup.** Two processes are
polling the same bot token: only one `getUpdates` consumer may exist per bot,
otherwise they steal messages from each other. Find who runs the other one
and stop it there; the newcomer refuses on purpose and never kills anything.

**MCP connects but no messages arrive in the session.** The commonest failure,
and it looks identical in all four cases: healthy server, dead channel.

- The channel flag is missing entirely (step A3 / B5).
- You used `--channels` instead of `--dangerously-load-development-channels`.
- You used the wrong entry for your path: `server:zalo` on a plugin install,
  or `plugin:zalo@zalo-bot-mcp` on a package install.
- Path B only: Claude Code was started outside the directory holding
  `.mcp.json`.

**`invalid choice: 'policy'`** means you are on a build older than the one
that added the command. Upgrade (`uv tool upgrade zalo-bot-mcp`, or
`/plugin update zalo@zalo-bot-mcp`).

**`cannot read ~/.zalo-bot-mcp/access.json`** means the file is not valid
JSON, almost always after a hand-edit. Fix the syntax, or delete the file to
start over from defaults (`pairing`, nobody allowed) and re-approve yourself.
Use `zalo-bot-mcp-admin policy` rather than editing the file by hand.
