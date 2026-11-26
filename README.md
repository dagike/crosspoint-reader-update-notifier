# CrossPoint update notifier

If a CrossPoint build changes for a device that you choose, this program sends a Discord message. It reads the public API at https://updates.crosspointreader.com/v3/components.json. It can also watch the [GitHub releases](https://github.com/crosspoint-reader/crosspoint-reader/releases) of CrossPoint.

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
- `ignore_text`: list of words. The program drops any part of a version text that contains one of them, so a change there does not send a message. For example, `["Indic"]` ignores the Indic Language Support entry in a shared Beta text.
- `include_changelog`: if `true`, the message includes the "What's new" text from the status site feed. The default is `true`. If the feed has no entry for the version, the message has no changelog.
- `notify_on_first_run`: if `true`, the first run sends a message for every selected channel. The default is `false`.
- `release_assets`: devices to watch in the GitHub releases. The default is `{}`, which turns this check off. See [GitHub releases](#github-releases).

## GitHub releases

The status feed does not list every build. For example, it does not list release candidates (test builds before a final release). If a new GitHub release or release candidate has a file for your device, the program sends a message. You do not need a GitHub account or token.

```json
"release_assets": {"Boox Picco": "picco"}
```

The name on the left is the label in the message. The text on the right must be part of the release file name, for example `picco` in `crosspoint-2.1.0rc-picco.bin`. Use text that matches only your device. For example, `x4` also matches the files for other X4 models, so use `x3-x4` for the X3 and X4.

On the first check of a device, the program saves the newest release and sends no message. If `notify_on_first_run` is `true`, it sends a message. GitHub allows 60 requests per hour from one IP address without a token. The program uses one request for each check.

## Commands

- `python3 notifier.py --list` prints all devices, channels, versions, and the newest GitHub releases.
- `python3 notifier.py --test` sends one test message.
- `python3 notifier.py --once` checks one time and exits.

Outside Docker, set `CONFIG_PATH` and `STATE_PATH` to local files and export `DISCORD_WEBHOOK_URL`.

## Uptime Kuma

To get an alert when the notifier stops, add a push monitor in Uptime Kuma.

1. In Uptime Kuma, click Add New Monitor and set Monitor Type to Push.
2. Set Heartbeat Interval to a value larger than `interval_seconds`, for example 1200 seconds.
3. Copy the Push URL that Uptime Kuma shows. Remove the part after the token, so that the URL ends with `/api/push/<token>`.
4. Put the URL in `.env` as `UPTIME_KUMA_PUSH_URL=`.
5. Run `docker compose up -d`.

After each successful check, the notifier sends an up heartbeat. If a check fails, it sends a down heartbeat with the error text.
