# Setup

Everything the bot needs is four values: a bot token, the group id, an RPC
endpoint and, for instant posts, its WebSocket twin.

## 1. Create the bot

Talk to [@BotFather](https://t.me/BotFather):

1. `/newbot`, pick a name and a username, copy the token it gives you.
2. `/setprivacy`, pick your bot, choose **Disable**. Group privacy is on by
   default, which hides group messages from the bot. With it on the bot still
   posts buys, but it never sees `/status` or any other command typed in the
   group.

Optional but nice: `/setcommands`, then paste

```
status - bot health and settings
stats - today's buys and leaderboard
test - post a sample buy
pause - stop posting
resume - start posting again
```

## 2. Add it to the group

Add the bot as an **administrator**. It needs permission to post messages, and
to pin messages if you want `/toggle pinwhales`.

The bot refuses to start if `CHAT_ID` is not a group, and warns in the log if it
is not an admin there.

## 3. Find the group id

Any of these work:

- Forward one message from the group to [@userinfobot](https://t.me/userinfobot).
- Post something in the group, then open
  `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `message.chat.id`.
- Open the group in Telegram Web; the number in the URL is the id without the
  `-100` prefix.

Supergroup ids are negative and start with `-100`, for example
`-1001234567890`.

## 4. Get an RPC endpoint

Any Ethereum mainnet provider works. For instant posts you want one that offers
WebSocket subscriptions: Alchemy, Infura, QuickNode, or your own node.

```env
RPC_HTTP=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
RPC_WS=wss://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
```

`RPC_WS` is optional. Without it the bot polls `RPC_HTTP` every `POLL_SECONDS`,
which is fine but not instant.

Public endpoints are usable for testing and the client adapts to their limits,
but they are not suitable for production. Measured against the free tiers:

| Endpoint | Limitation |
| --- | --- |
| publicnode | rejects historical `eth_getLogs` without a token |
| 1rpc.io | caps `eth_getLogs` at 50 blocks |
| drpc.org | caps JSON-RPC batches at 3 requests |
| ankr, cloudflare | require a key, or refuse the request |

The client discovers both the range cap and the batch cap at runtime and
degrades instead of failing, so a capped provider still works, just slower.

## 5. Configure

```sh
cp .env.example .env
```

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `BOT_TOKEN` | yes | | from BotFather |
| `CHAT_ID` | yes | | negative group id |
| `RPC_HTTP` | yes | | http or https |
| `RPC_WS` | no | | ws or wss, enables instant posts |
| `TOKEN_ADDRESS` | no | NOX | any ERC-20 |
| `PAIR_ADDRESS` | no | NOX/WETH | its Uniswap V2 pair |
| `ADMIN_IDS` | no | | extra admins beyond the group's own |
| `CONFIRMATIONS` | no | `0` | blocks to wait before posting |
| `POLL_SECONDS` | no | `4` | polling interval, 1 to 120 |
| `STATE_FILE` | no | `./state.json` | |
| `MEDIA_DIR` | no | `./media` | |
| `WEBSITE` | no | nonos.software | footer link |
| `LOG_LEVEL` | no | `INFO` | DEBUG, INFO, WARNING, ERROR |

Every value is validated at start. A malformed token, a non-numeric chat id or
an out-of-range interval stops the bot immediately with a one line reason,
rather than failing silently at the first buy.

## 6. Media

```sh
python3 tools/make_media.py
```

This renders `media/buy-small`, `buy-medium`, `buy-large` and `buy-whale` as
both MP4 and GIF from the NOX logo. `--size`, `--frames` and `--fps` change the
output; `--only whale` rebuilds one tier. If the directory is missing the bot
posts text only and says so in the log.

## 7. Run

```sh
python3 -m buybot
```

At start it prints the pair, the current price, market cap and liquidity, then
begins watching. `/status` in the group confirms the cursor is keeping up.

For a permanent install see [deployment.md](deployment.md).

## Tracking a different token

Set `TOKEN_ADDRESS` and `PAIR_ADDRESS` to the token and its Uniswap V2 pair.
The bot reads the symbol, decimals and token ordering from the chain, so
nothing else changes. Uniswap V3 pools use a different event and are not
supported.
