# Media and emoji

## The four animations

`tools/make_media.py` renders one animation per size tier from the NOX logo,
in brand teal `#57EFE0` on a dark grid:

| Tier | Default range | Animation |
| --- | --- | --- |
| small | under $250 | logo with a slow pulsing glow |
| medium | $250 to $1,000 | pulse with rising particles |
| large | $1,000 to $5,000 | the logo lifts on an exhaust plume |
| whale | $5,000 and up | logo bobbing over layered waves and spray |

```sh
python3 tools/make_media.py                    # all four, MP4 and GIF
python3 tools/make_media.py --only whale       # one tier
python3 tools/make_media.py --size 640 --fps 24 --frames 48
```

The logo is rasterised from `media/nox-logo.svg` with `rsvg-convert` when it is
available, and falls back to `media/nox-badge.png` when it is not. GIFs are
written with Pillow; the MP4s need `ffmpeg` on the path and are skipped without
it. The bot prefers the MP4, which is smaller and loops more smoothly in
Telegram, and falls back to the GIF and then to the badge image.

At default settings each file is well under a megabyte, against Telegram's
50 MB upload limit.

## Replacing them

You do not need to touch the server. Send the GIF or video in the group, reply
to it with `/setmedia whale`, and the bot stores Telegram's `file_id` in
`state.json`. Nothing is uploaded again after that, for that tier or any other
using the same file.

`/setmedia all` sets one file for every tier, `/clearmedia` restores the
bundled animations. Supported: animations, videos, photos, stickers, and
documents with GIF or MP4 mime types.

Uploaded local files are also cached: the first post of a tier uploads the
file, the response carries a `file_id`, and that id is reused from then on.

## Premium emoji

Telegram's premium emoji are custom emoji packs. The bot can put one in the buy
bar so a NOX logo repeats across the message instead of a green circle.

Build and publish the pack:

```sh
python3 tools/make_emoji.py                                # writes media/emoji-nox.png
python3 tools/make_emoji.py --create --owner <user id>     # publishes the pack
```

The script renders a 100x100 transparent PNG, uploads it, creates a custom
emoji set owned by the user id you pass, and prints the resulting
`custom_emoji_id` along with the `t.me/addemoji/...` link. Re-running it adds
to the existing pack rather than failing.

Then, in the group, reply to any message containing that emoji with
`/setemoji`. `/emojiid` lists the ids in a message if you want to record one.

### The Fragment rule

A bot may only **send** custom emoji if it owns a collectible username bought
on [Fragment](https://fragment.com). Assign the username to the bot in
BotFather under Bot Settings, Usernames.

Without one, Telegram rejects the message with a 400. The bot notices this the
first time, remembers it for the session, strips the custom emoji tags and
sends the plain emoji instead. The buy is never lost. `/status` shows
`Premium emoji allowed: yes` or `no`.

This restriction is on sending only. Premium members of your group can use the
pack you published in their own messages either way.

## Message length

Telegram caps a media caption at 1024 characters, and HTML tags count. Each
custom emoji costs about 45 characters because of its `<tg-emoji>` wrapper,
against one or two for a plain emoji.

The renderer builds the fixed part of the message first, measures what is left
and sizes the bar to fit. A whale buy with badges, six extra links and premium
emoji still lands inside the limit, which the test suite checks.
