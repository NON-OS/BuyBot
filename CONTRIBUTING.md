# Contributing

Bug reports, fixes and features are all welcome.

## Before you open a pull request

```sh
python3 -m unittest discover -s tests -t .
ruff check buybot tools tests
```

Both run in CI on every push, across Python 3.9 through 3.13.

## What the code looks like

- One concern per file. If a module passes roughly 200 lines it usually wants
  splitting.
- Comments explain why, never what. If a comment restates the line below it,
  delete the comment.
- No new runtime dependencies without a good reason. Today it is aiohttp,
  websockets and Pillow, and that is deliberate.
- Type hints on anything public.
- Never log a bot token or an RPC URL. Both carry secrets and both have a
  redaction helper already.

## Tests

New behaviour needs a test, and it must not touch the network. The suite uses
fake RPC and Telegram objects; see `tests/test_swaps.py` and
`tests/test_poster.py` for the pattern.

Bug fixes should come with the test that fails without the fix.

## Commits

Short imperative subject, under about 70 characters, no trailing period. A
body only when the change needs one, wrapped at 72 characters, explaining why
rather than what.

```
Reset the buy streak when a sell lands

The streak counted buys since start, so it kept growing through a
sell-off and the badge stopped meaning anything.
```

## Reporting a bug

Include the bot version, the Python version, your RPC provider, and the
relevant log lines with the token and RPC URL removed. `/status` output helps.

## Security

Do not open a public issue for a security problem. Mail ekisanon@proton.me
instead.
