# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Use GitHub's private
vulnerability reporting instead:

**[Report a vulnerability](https://github.com/trongnguyenbinh/zalo-bot-mcp/security/advisories/new)**

This is a one-person project. I will acknowledge your report within **7 days** and agree a
disclosure timeline with you from there. Only the latest release is supported; fixes land
there, not in older versions.

## What counts

This server hands messages from a chat app to an agent session that can read files and run
commands. The security boundary is the **gate**: the code that decides whose messages reach
the session at all.

**In scope.** Anything that gets a message past the gate, or changes who is allowed through,
without the operator typing a command in their own terminal:

- A Zalo message that causes the allowlist, pairing state, or any access config to change.
- Reaching the session from a chat ID or user ID that was never approved.
- Getting a reply delivered to a chat that never messaged the bot.
- Leaking the bot token into logs, error messages, tracebacks, or files.
- A crafted update payload that crashes the poller or bypasses deduplication.

**Out of scope.** These are the design working as intended, not vulnerabilities:

- Someone on the allowlist asking the agent to do something harmful. Allowlisted people are
  trusted by definition; that is what approving them means.
- The agent session having filesystem and shell access. That is the entire point of the
  project, and it is why the allowlist should stay short.
- Prompt injection *inside* an allowlisted conversation. The gate controls who talks to the
  session, not what a trusted person says.
- Limits, outages, or behaviour changes in Zalo's own API.
- Anything requiring the attacker to already have your bot token or local machine access.

If you are unsure which side of the line something falls on, report it privately anyway.

## For operators

- The bot token is a credential. Anyone holding it can read every message sent to your bot
  and send messages as it. Keep it in `<state_dir>/.env` at mode 0600, never in a repo, and
  rotate it at <https://bot.zapps.me/> if it is ever pasted into a chat, log, or issue.
- Keep the allowlist short. Access to the bot is access to a session that can run commands.
- Access is granted only from your terminal. No message, from anyone, can grant it. If a
  message asks you to approve someone, treat that as the attack it looks like.
- **Never paste raw logs into an issue** without checking them for your token first.
