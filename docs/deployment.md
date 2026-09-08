# Deployment

The bot is a single long lived process. It needs outbound HTTPS to
`api.telegram.org` and to your RPC provider, and a writable path for
`state.json`. No inbound ports, no database.

## systemd

```sh
sudo useradd -r -s /usr/sbin/nologin nox
sudo mkdir -p /opt/nox-buybot
sudo cp -r . /opt/nox-buybot
sudo chown -R nox:nox /opt/nox-buybot
sudo chmod 600 /opt/nox-buybot/.env

sudo -u nox python3 -m pip install --user -r /opt/nox-buybot/requirements.txt
sudo -u nox python3 /opt/nox-buybot/tools/make_media.py

sudo cp deploy/nox-buybot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nox-buybot
```

Watch it come up:

```sh
journalctl -u nox-buybot -f
```

The unit restarts on failure with a five second delay, and runs with
`NoNewPrivileges` and `ProtectSystem=strict`, with only its own directory
writable. Secrets come from `EnvironmentFile`, so they are not visible in the
process arguments.

## Docker

```sh
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f
```

The image installs `librsvg2-bin` and `ffmpeg` and renders the animations at
build time, so the container ships with its media. State lives in a named
volume, which keeps the cursor and settings across upgrades.

## Upgrading

```sh
sudo systemctl stop nox-buybot
sudo -u nox git -C /opt/nox-buybot pull
sudo systemctl start nox-buybot
```

Do not delete `state.json`. It holds the block cursor, and losing it means the
bot restarts from the current head. That skips buys rather than duplicating
them, but the daily counters and the tracked all time high are lost too.

Downtime is safe. The cursor persists, so on restart the bot scans everything
it missed, up to 2000 blocks per pass, and posts those buys. If the outage was
long and you would rather not flood the group, `/pause` before restarting, then
let it catch up and `/resume`.

## What to watch

`/status` in the group is the fastest check. The cursor should track the head
within a block or two.

In the logs, one line per posted buy, and:

| Line | Meaning |
| --- | --- |
| `ws logs dropped ... reconnecting` | normal if occasional, a problem if constant |
| `eth_getLogs range rejected` | the provider caps ranges, the client adapted |
| `provider rejected batch` | batching disabled for this session, calls now sequential |
| `flood wait Ns` | Telegram rate limit, the send is retried |
| `custom emoji rejected` | the bot has no Fragment username, plain emoji from now on |
| `scan failed at head N` | one scan failed, retried on the next block |

A restart loop in `systemctl status` almost always means configuration: the
bot exits immediately with one line naming the variable it rejected.

## Cost

The bot makes a handful of RPC calls per buy and two per block for the cursor.
A free provider tier covers a quiet token comfortably. If you are rate limited,
raise `POLL_SECONDS` and rely on the WebSocket path, which does not consume
request quota on most providers.

## Running two bots

Two tokens for two groups can share a machine. Give each its own `STATE_FILE`
and its own unit name. They can share the same RPC endpoint.

## Security notes

- `.env` holds the bot token and an RPC key. Keep it at mode 600 and out of
  version control; `.gitignore` already excludes it.
- The bot never echoes the token or the RPC URL, including in error messages.
- It writes `state.json` at mode 600, atomically.
- It only accepts commands from administrators of the configured chat, and only
  from that chat or a private message.
- It needs no private key and cannot move funds. It only reads the chain.
