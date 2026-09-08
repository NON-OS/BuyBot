# Architecture

The bot turns Uniswap V2 `Swap` events into Telegram messages. This document
follows one buy from the chain to the group and then explains why each part is
built the way it is.

## The path of a buy

```
node pushes Swap log
        │
        ▼
   Watcher.fast_path        coalesces 250 ms of logs from the same block
        │
        ▼
   Swaps.from_logs          groups by transaction, keeps buy-side swaps
        │                   fetches tx, block and market in parallel
        ▼
   Watcher.handle_buy       deduplicates, applies the minimum, records badges
        │
        ▼
   Poster.post              picks the tier's media, renders, sends
        │
        ▼
      Telegram
```

## Three loops, one handler

A single subscription is not enough. Sockets drop, providers restart, the
process gets redeployed. Three sources run at once and all of them call
`handle_buy`:

**Fast path.** `eth_subscribe("logs")` filtered to the pool address and the
`Swap` topic. The node pushes the log as soon as it has the block, so nothing
is waited for. This is the path that posts in normal operation.

**Head scan.** `eth_subscribe("newHeads")` advances a block cursor. For every
new head the bot asks `eth_getLogs` for everything since the last cursor
position and processes what it finds. If the log subscription missed something,
this catches it within one block.

**Slow poll.** `eth_blockNumber` on a long interval, driving the same cursor
scan. This is the backstop for a provider whose subscriptions go quiet without
closing the socket.

Duplicate work is expected and harmless. `State.record` keeps the last 500
transaction hashes and returns `None` for one it has already handled, so the
second and third source find nothing to do.

The cursor is the durability mechanism. It is written to `state.json` after
every scan, so a restart resumes from the last processed block rather than from
the head. On a first run the cursor starts at the current head, so the bot does
not replay history into the group.

## Reading a swap

Uniswap V2 emits one event for both directions:

```solidity
Swap(address indexed sender,
     uint amount0In, uint amount1In,
     uint amount0Out, uint amount1Out,
     address indexed to)
```

Which side is the token depends on the pair's token ordering, read once at
start via `token0()`. A buy has ETH in and token out; a sell is the mirror, and
is counted (it resets the buy streak) but not posted.

One transaction can produce several `Swap` events on the same pair, because
routers and aggregators split a fill across paths. Grouping by transaction hash
before rendering turns four log lines into one message that shows the true
total. The message keeps the count in `swaps` for anyone reading the data.

The `to` field in the log is usually the router, not the person. The bot reads
the transaction and uses `from` as the buyer, so a buy through 1inch, Matcha or
a sniper bot is attributed to the wallet that made it.

## New holders and position

Both come from `balanceOf` at two blocks: the block before the buy and the
block of the buy. A prior balance of zero is a new holder. Otherwise the
percentage increase is the position change. This is exact, and it costs two
`eth_call`s that ride along in the same batch as everything else.

## Prices

Everything is read at the buy's own block, not at head, so a message about a
buy from twenty blocks ago shows the market as it was then.

- Price comes from the pool reserves via `getReserves()`.
- ETH/USD comes from the Chainlink mainnet aggregator, not from a price API.
  No API key, no rate limit, no outage.
- Market cap is `totalSupply` minus the balances of the zero and dead
  addresses, times price.

`Decimal` context is raised to 60 digits at import, because raw uint256 token
amounts exceed the default 28 significant digits and would otherwise be
silently rounded.

## Round trips per buy

For one transaction the bot issues:

1. one batch: the transaction, the block header, and the market snapshot, all
   concurrent
2. one batch: two `balanceOf` calls

That is two waits, not eight, because `asyncio.gather` overlaps them. Media is
uploaded once and cached by `file_id`, so later posts of the same tier send a
short string rather than a file.

## Provider differences

Free and paid endpoints disagree about limits, and they express the
disagreement as errors rather than as a capability list. Two limits are
discovered at runtime:

**Batch size.** If a provider rejects a batch, the client drops to sequential
calls for the rest of the session. It distinguishes a batch limit from a real
error, so a reverted call is still an error.

**Log range.** If `eth_getLogs` refuses a range, the window is quartered and
retried until it is accepted, down to ten blocks. The scan continues from where
it stopped, so a shrinking window never skips a block. Errors that are not
about range are raised rather than absorbed.

## Reorgs

When a reorg drops a block the node sends the log again with `removed: true`.
The bot deletes the message it posted for that transaction, removes it from the
counters and forgets the hash, so if the transaction is mined again it is
posted again. Message ids are kept for the last 200 posts.

## Failure behaviour

- A failed Telegram send is logged and skipped; the cursor still advances, so
  one bad message cannot wedge the bot.
- A media send rejected with 400, usually a stale `file_id`, drops the cached
  id and retries as text, so the buy is still announced.
- A failed scan leaves the cursor where it was and retries on the next block.
- A dropped WebSocket reconnects with backoff, and the cursor covers the gap.
- Telegram flood waits are honoured, capped at two minutes.
- An unreadable `state.json` is logged and replaced by defaults rather than
  crashing on boot.

## Secrets

The bot token and the RPC URL, which usually carries an API key, are redacted
from every log line the bot writes. `state.json` is written with mode 600
through a temporary file and an atomic rename.

## Module map

| Module | Responsibility |
| --- | --- |
| `config` | environment parsing and validation |
| `rpc` | JSON-RPC, batching, subscriptions, provider adaptation |
| `abi`, `keccak` | selectors, decoding, EIP-55 checksums |
| `chain` | pair metadata and market snapshots |
| `swaps` | Swap logs to `Buy` objects |
| `models` | `PairInfo`, `Market`, `Buy` |
| `state` | settings, cursor, dedupe, daily counters |
| `render`, `format`, `routers` | message text and keyboard |
| `telegram`, `media` | Bot API client and media handling |
| `poster` | tier media selection and sending |
| `watcher` | the three loops and buy handling |
| `status` | `/status` and `/stats` text |
| `commands/` | authorisation, dispatch, handlers |
| `app` | wiring, preflight checks, shutdown |

Dependencies point one way: `app` knows everything, `watcher` knows `swaps` and
`poster`, and the leaves know nothing about the rest. No module imports `app`.
