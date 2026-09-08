# BuyBot

A Telegram buy tracker for NOX on Ethereum mainnet. It watches the Uniswap V2
NOX/WETH pool and posts every buy to the community group as the block lands,
with tiered animations, a size-scaled emoji bar, new holder detection, whale
alerts and a daily leaderboard.

Written for the NOX group, but it tracks any Uniswap V2 pair: set two addresses
and it works.

```
Token  0x0a26c80Be4E060e688d7C23aDdB92cBb5D2C9eCA
Pool   0x07CE5889D2EB681Af3bD61db24Ab2602c502Bd1B
```

## A post

```
💚 NOX BUY!
🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢

💵 Spent: 0.1841 ETH ($461.04)
🪙 Got: 168,442 NOX
👤 Buyer: 0x610e…28AF | Txn
🆕 New Holder!
📊 Price: $0.002743
💧 Liquidity: $171,466
🏦 Market Cap: $2.18M
🔀 Via: Uniswap
🏆 NEW ATH · 🔥 Biggest buy today · ⚡ 7 buy streak

📈 Chart | 🦄 Buy | 🌐 Website
[ 🦄 Buy NOX ] [ 📈 Chart    ]
[ 🔍 Txn     ] [ 🧭 DEXTools ]
```

Each buy carries the animation for its size tier. All four are generated from
the NOX logo by `tools/make_media.py`, and any of them can be replaced from
inside Telegram by replying to a GIF with `/setmedia`.

## Install

Python 3.9 or newer. Three dependencies: aiohttp, websockets, Pillow. No web3,
no database.

```sh
git clone https://github.com/NON-OS/BuyBot
cd BuyBot
python3 -m pip install -r requirements.txt
cp .env.example .env          # fill in BOT_TOKEN, CHAT_ID, RPC_HTTP, RPC_WS
python3 tools/make_media.py   # renders media/buy-*.mp4 and .gif
python3 -m buybot
```

[docs/setup.md](docs/setup.md) walks through the bot token, the group id and
the RPC endpoint. [docs/deployment.md](docs/deployment.md) covers systemd and
Docker.

Send `/test 2500` in the group to see a large tier post, and `/status` for
health.

## Speed

The bot subscribes to the pool's Swap logs over WebSocket, so the node pushes
each buy instead of the bot asking for it. There is no polling interval on that
path and no confirmation wait by default.

Two loops run behind it. New block headers advance a cursor through
`eth_getLogs`, and a slow poll covers the case where both subscriptions stall.
Every path funnels into the same handler, which deduplicates by transaction
hash, so a dropped socket or a restart cannot lose a buy or post one twice.

Reorgs are handled: when the node retracts a log, the bot deletes the message
and rolls back the counters.

[docs/architecture.md](docs/architecture.md) explains the whole pipeline.

## Commands

Group admins, in the group or in a private chat with the bot.

| Command | Effect |
| --- | --- |
| `/status` | health, cursor lag, current settings |
| `/stats` | today's buys, volume, new holders, top five buyers |
| `/test [usd]` | post a sample buy of that size |
| `/pause`, `/resume` | stop or start posting, tracking continues |
| `/setemoji 🟢` | bar emoji, or reply to a premium emoji to use it |
| `/setstep 25` | USD per emoji in the bar |
| `/setmax 60` | cap on bar length |
| `/setmin 25` | ignore buys below this value |
| `/settier whale 5000` | tier thresholds: medium, large, whale |
| `/setmedia whale` | reply to a GIF, MP4, photo or sticker |
| `/clearmedia [tier]` | back to the bundled animations |
| `/toggle position\|market\|buttons\|pinwhales` | show or hide blocks, pin whale buys |
| `/addlink Trending https://...` | extra footer link, six at most |
| `/dellink Trending` | remove one |
| `/emojiid` | reply to a message to list its custom emoji ids |

Settings live in `state.json` and survive restarts. Full reference in
[docs/commands.md](docs/commands.md).

## Premium emoji

`tools/make_emoji.py --create --owner <your user id>` publishes the NOX logo as
a custom emoji pack and prints its id. Reply to the emoji with `/setemoji` and
the bar switches to it.

Telegram only renders custom emoji sent by a bot that owns a collectible
username bought on Fragment. Without one the bot detects the rejection once and
sends the standard emoji instead, and `/status` reports which is in effect.
Details in [docs/media.md](docs/media.md).

## Tests

```sh
python3 -m unittest discover -s tests -t .
```

67 tests, no network access. They cover swap decoding, split fills, sells,
reorgs, provider limits, command authorisation, message escaping and the
caption size limit.

## Layout

```
buybot/config.py       environment, validated at start
buybot/rpc.py          JSON-RPC and WebSocket subscriptions
buybot/abi.py          selectors, decoding, EIP-55
buybot/keccak.py       Keccak-256 for the checksums
buybot/chain.py        pair metadata and market snapshot
buybot/swaps.py        Swap logs to buys
buybot/models.py       PairInfo, Market, Buy
buybot/state.py        settings, cursor, daily counters
buybot/render.py       message HTML and keyboard
buybot/format.py       money and address formatting
buybot/routers.py      known router addresses
buybot/telegram.py     Bot API client
buybot/media.py        media kinds and file ids
buybot/poster.py       posting and media selection
buybot/watcher.py      the three loops
buybot/status.py       /status and /stats text
buybot/commands/       admin commands
buybot/app.py          wiring and shutdown
```

## Numbers

Price and liquidity come from the pool reserves at the buy's own block. ETH/USD
comes from the Chainlink mainnet feed at that block, not from an API. Market
cap is total supply minus burn addresses. The buyer is the transaction sender,
so buys through routers, aggregators and smart wallets are attributed to the
person rather than to the contract.

## Contributing

Issues and pull requests welcome. Please read
[CONTRIBUTING.md](CONTRIBUTING.md); the short version is that tests must pass,
new behaviour needs a test, and files stay small and single purpose.

## License

MIT. See [LICENSE](LICENSE).
