#!/usr/bin/env python3
"""Send a Discord message when a CrossPoint build changes for chosen devices."""
import argparse
import html
import re
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://updates.crosspointreader.com/v3/components.json"
FEED_URL = "https://updates.crosspointreader.com/history.atom"
SITE_URL = "https://updates.crosspointreader.com"
USER_AGENT = "update-notifier/1.0"
MIN_INTERVAL = 120

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/data/config.json")
STATE_PATH = os.environ.get("STATE_PATH", "/data/state.json")


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def load_config():
    cfg = {
        "devices": ["*"],
        "channels": ["Stable"],
        "interval_seconds": 900,
        "notify_on_first_run": False,
        "ignore_text": [],
        "include_changelog": True,
    }
    cfg.update(load_json(CONFIG_PATH, {}))
    cfg["webhook"] = os.environ.get("DISCORD_WEBHOOK_URL", "")
    cfg["interval_seconds"] = max(MIN_INTERVAL, int(cfg["interval_seconds"]))
    return cfg


def fetch_components():
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["components"]


def clean_version(text, ignore):
    """Drop '; '-separated parts that contain any ignored text."""
    parts = [p.strip() for p in text.split(";")]
    kept = [p for p in parts if not any(i.lower() in p.lower() for i in ignore)]
    return "; ".join(kept)


def select_targets(components, cfg):
    devices = {d.lower() for d in cfg["devices"]}
    channels = {c.lower() for c in cfg["channels"]}
    all_devices = "*" in devices
    targets = []
    for parent in components:
        if not all_devices and parent["name"].lower() not in devices:
            continue
        for child in parent.get("children", []):
            if child["name"].lower() in channels:
                targets.append(
                    (
                        parent["name"],
                        child["name"],
                        child["id"],
                        clean_version(child["description"], cfg["ignore_text"]),
                    )
                )
    return targets


def warn_unknown(components, cfg):
    names = {p["name"].lower() for p in components}
    for d in cfg["devices"]:
        if d != "*" and d.lower() not in names:
            log(f"Warning: device '{d}' not found. Run --list to see names.")
    chans = {c["name"].lower() for p in components for c in p.get("children", [])}
    for c in cfg["channels"]:
        if c.lower() not in chans:
            log(f"Warning: channel '{c}' not found. Run --list to see names.")


def post_webhook(webhook, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        webhook,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=30):
                return True
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                try:
                    wait = float(json.load(e).get("retry_after", 5))
                except Exception:
                    wait = 5
                time.sleep(min(wait, 60))
                continue
            log(f"Discord error: HTTP {e.code}")
            return False
        except urllib.error.URLError as e:
            log(f"Discord error: {e.reason}")
            return False
    return False


def fetch_changelog(device, version):
    """Return (text, link) from the newest feed entry that mentions the version."""
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        feed = resp.read().decode("utf-8", "replace")
    parts = [p.strip().lower() for p in version.split(";") if p.strip()]
    found = []
    for entry in re.findall(r"<entry>(.*?)</entry>", feed, flags=re.S):
        title = html.unescape(re.search(r"<title>(.*?)</title>", entry, re.S).group(1))
        if not any(p in title.lower() for p in parts):
            continue
        body = re.search(r"<content[^>]*>(.*?)</content>", entry, re.S).group(1)
        body = body.replace("<![CDATA[", "").replace("]]>", "")
        body = body.split("</strong> -", 1)[-1]
        body = re.sub(r"<br\s*/?>", "\n", body)
        body = html.unescape(re.sub(r"<[^>]+>", "", body)).strip()
        link = re.search(r'rel="alternate"[^>]*href="([^"]+)"', entry)
        found.append((title, body, link.group(1) if link else SITE_URL))
    if not found:
        return None, None
    key = device.lower().replace("xteink ", "")
    pick = next((f for f in found if key in f[0].lower()), found[0])
    return pick[1], pick[2]


def send_update(webhook, device, channel, old, new, changelog=None, link=SITE_URL):
    embed = {
        "title": f"New CrossPoint build: {device} {channel}",
        "url": link,
        "color": 0x2ECC71,
        "fields": [
            {"name": "Old", "value": old or "none", "inline": True},
            {"name": "New", "value": new, "inline": True},
        ],
    }
    if changelog:
        embed["description"] = changelog[:1500]
    return post_webhook(webhook, {"embeds": [embed]})


def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def check(cfg, first_run_ref):
    components = fetch_components()
    targets = select_targets(components, cfg)
    state = load_json(STATE_PATH, None)
    first_run = state is None
    state = state or {}
    changed = False
    for device, channel, cid, version in targets:
        prev = state.get(cid, {}).get("version")
        if prev == version:
            continue
        if prev is None and first_run and not cfg["notify_on_first_run"]:
            ok = True
        else:
            text, link = None, SITE_URL
            if cfg["include_changelog"]:
                try:
                    text, link = fetch_changelog(device, version)
                except Exception as e:
                    log(f"Changelog unavailable: {e}")
            ok = send_update(
                cfg["webhook"], device, channel, prev, version, text, link or SITE_URL
            )
            if ok:
                log(f"Notified: {device} {channel} {prev} -> {version}")
        if ok:
            state[cid] = {"device": device, "channel": channel, "version": version}
            changed = True
    if changed or first_run:
        save_state(state)
    if first_run:
        log(f"First run: saved {len(state)} versions.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="check once and exit")
    ap.add_argument("--list", action="store_true", help="list devices and channels")
    ap.add_argument("--test", action="store_true", help="send a test message")
    args = ap.parse_args()

    if args.list:
        for p in fetch_components():
            print(p["name"])
            for c in p.get("children", []):
                print(f"  {c['name']}: {c['description']}")
        return 0

    cfg = load_config()
    if not cfg["webhook"]:
        log("Error: DISCORD_WEBHOOK_URL is not set.")
        return 1

    if args.test:
        ok = post_webhook(
            cfg["webhook"], {"content": "CrossPoint update notifier test message."}
        )
        log("Test message sent." if ok else "Test message failed.")
        return 0 if ok else 1

    try:
        warn_unknown(fetch_components(), cfg)
    except Exception as e:
        log(f"Could not check names: {e}")

    while True:
        try:
            check(cfg, None)
        except Exception as e:
            log(f"Check failed: {e}")
        if args.once:
            return 0
        time.sleep(cfg["interval_seconds"])


if __name__ == "__main__":
    sys.exit(main())
