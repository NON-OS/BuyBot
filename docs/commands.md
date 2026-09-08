# Commands

All commands except `/help` require administrator rights. The bot accepts them
in the configured group, and in a private chat from anyone who is an admin of
that group. Commands sent from any other group are ignored, as are commands
addressed to a different bot with `@othername`.

Administrators are read from the group itself and cached for ten minutes.
`ADMIN_IDS` in the environment adds user ids that are always allowed, which is
useful if you want to change settings without being a visible admin.

Every value is bounds checked. A rejected value leaves the setting untouched
and answers with the accepted range.

## Status

**`/status`** reports uptime, the current head, the cursor and how many blocks
behind it is, whether posting is live or paused, the total posted, the current
thresholds, which media is in use, whether Telegram accepts custom emoji from
this bot, and the RPC host with its discovered batch and log range limits.

A cursor lag of zero or one is normal. A lag that grows means the RPC is slow
or rate limiting.

**`/stats`** shows today's buys, volume, new holders and biggest buy in UTC,
the tracked all time high price, and the top five buyers of the day by total
spend. `/leaderboard` is the same command.

Daily counters reset at midnight UTC. The all time high is tracked from the
first buy the bot ever saw, not from the token's launch.

## Posting

**`/test [usd]`** posts a sample buy at the current price. Default `$500`,
range `$1` to `$10,000,000`, at most one every ten seconds. It uses the tier
media the real buy of that size would use, which makes it the quick way to
check a new GIF.

**`/pause`** stops posting. Buys are still tracked, the cursor still advances,
and the counters still move, so `/stats` stays correct and nothing is replayed
when you resume. **`/resume`** starts posting again.

## Size and tiers

**`/setmin 25`** ignores buys below that value in USD. They are still counted.

**`/setstep 25`** sets how many dollars one emoji in the bar represents.
**`/setmax 60`** caps the bar. The bar is also trimmed automatically to keep
the whole message inside Telegram's 1024 character caption limit, so a very
large buy will not be dropped for length.

**`/settier medium|large|whale <usd>`** moves a tier threshold. The three must
stay in order, medium below large below whale, and a change that breaks the
order is refused. Defaults are `$250`, `$1,000` and `$5,000`.

Tiers decide two things: which animation is posted, and the title of the
message. The whale tier can also pin, see `/toggle`.

## Appearance

**`/setemoji 🟢`** sets the bar emoji. Reply to a message containing a premium
emoji and send `/setemoji` with no argument to use that one instead; see
[media.md](media.md) for what Telegram allows there.

**`/emojiid`** replies with the custom emoji ids in the message you replied to,
which is how you find an id to keep.

**`/toggle <what>`** flips one of:

| Name | Effect |
| --- | --- |
| `position` | the New Holder and Position lines |
| `market` | price, liquidity and market cap |
| `buttons` | the inline keyboard |
| `pinwhales` | pin every whale buy |

**`/addlink Name https://...`** adds a link to the footer, six at most. Only
http, https and tg links are accepted. **`/dellink Name`** removes one.

## Media

**`/setmedia <tier|all>`** as a reply to a GIF, MP4, photo or sticker sets that
media for the tier. The bot stores Telegram's `file_id`, so nothing is
uploaded twice and the file never has to exist on the server.

**`/clearmedia <tier|all>`** goes back to the bundled animation for that tier.

Stickers are supported, with one Telegram quirk: a sticker cannot carry a
caption, so the bot sends the sticker first and the text right after it.

## Where settings live

`state.json` next to the project, or wherever `STATE_FILE` points. It holds the
settings, the media ids, the block cursor, the recent transaction hashes, the
posted message ids and today's counters. It is written atomically with mode
600 after every command and every scan.

You can edit it while the bot is stopped. Unknown keys are ignored and a
corrupt file is replaced by defaults with a line in the log, so an old file
from a previous version will not stop the bot from starting.
