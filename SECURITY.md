# Security

## Reporting

Mail ekisanon@proton.me. Do not open a public issue.

Please include what you found, how to reproduce it and what an attacker gets
out of it. Expect a first reply within a few days.

## Scope

The bot reads the chain and writes to one Telegram chat. It holds no private
key and cannot move funds. The two secrets it does hold are the Telegram bot
token and the RPC URL, which usually contains an API key.

Worth reporting:

- anything that leaks the bot token or the RPC URL, including into logs
- a way to run admin commands without being an admin of the configured chat
- injection into a posted message through on-chain data such as a token symbol
- a crash or a hang reachable from chain data or from a Telegram update

## What is already handled

- Commands are accepted only from administrators of the configured chat, and
  only in that chat or in a private message.
- Every dynamic value in a message is HTML escaped, including the token symbol,
  the configured emoji and the footer links.
- The token and the RPC URL are stripped from log output.
- `state.json` is written at mode 600, atomically, and a corrupt file is
  replaced by defaults rather than crashing the process.
- Every setting is bounds checked, so an admin typo cannot produce a message
  that Telegram rejects.
