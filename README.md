# CrossPoint update notifier

If a CrossPoint build changes for a device that you choose, this program sends a Discord message. It reads the public API at https://updates.crosspointreader.com/v3/components.json.

## Setup

1. In Discord, open the channel settings, go to Integrations, and create a webhook. Copy the webhook URL.
2. Copy `.env.example` to `.env` and paste the URL after `DISCORD_WEBHOOK_URL=`.
3. Create the folder `data` and copy `config.example.json` to `data/config.json`.
4. Run `python3 notifier.py --list` to see the exact device and channel names.
5. Edit `data/config.json` so that `devices` and `channels` list the names that you want.
6. Run `docker compose up -d --build`.

## Configuration

- `devices`: list of device names, or `["*"]` for all devices.
- `channels`: list of channel names. The default is `["Stable"]`. Other names are `Beta`, `Nightly`, `Stock English`, and `Stock Chinese`.
- `interval_seconds`: time between checks. The default is 900 and the minimum is 120.
- `notify_on_first_run`: if `true`, the first run sends a message for every selected channel. The default is `false`.

## Commands

- `python3 notifier.py --list` prints all devices, channels, and versions.
- `python3 notifier.py --test` sends one test message.
- `python3 notifier.py --once` checks one time and exits.

Outside Docker, set `CONFIG_PATH` and `STATE_PATH` to local files and export `DISCORD_WEBHOOK_URL`.
