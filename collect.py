#!/usr/bin/env python3
"""AI Digest Collector - Fetches latest updates from RSS feeds and Twitter."""

import asyncio
import json
import sqlite3
import hashlib
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

DIR = Path(__file__).parent
DB_PATH = DIR / "seen.db"
CONFIG_PATH = DIR / "config.json"
OUTPUT_PATH = DIR / "latest.json"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            hash TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            ts REAL
        )
    """)
    conn.commit()
    return conn


def is_seen(conn, item_hash):
    row = conn.execute("SELECT 1 FROM seen WHERE hash=?", (item_hash,)).fetchone()
    return row is not None


def mark_seen(conn, item_hash, source, title):
    conn.execute(
        "INSERT OR IGNORE INTO seen (hash, source, title, ts) VALUES (?,?,?,?)",
        (item_hash, source, title, time.time()),
    )
    conn.commit()


def hash_item(source, title, link):
    return hashlib.md5(f"{source}|{title}|{link}".encode()).hexdigest()


def collect_rss(config, conn, cutoff_ts):
    items = []
    for src in config["rss_sources"]:
        try:
            feed = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                if count >= config.get("max_items_per_source", 5):
                    break

                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")[:500]
                published = entry.get("published_parsed") or entry.get("updated_parsed")

                if published:
                    entry_ts = time.mktime(published)
                    if entry_ts < cutoff_ts:
                        continue

                h = hash_item(src["name"], title, link)
                if is_seen(conn, h):
                    continue

                items.append({
                    "source": src["name"],
                    "type": src["type"],
                    "focus": src["focus"],
                    "title": title,
                    "link": link,
                    "summary": summary,
                })
                mark_seen(conn, h, src["name"], title)
                count += 1
        except Exception as e:
            print(f"[WARN] RSS fetch failed for {src['name']}: {e}")
    return items


async def collect_twitter(config, conn):
    """Try twscrape; returns empty list if no accounts configured."""
    items = []
    accounts_db = DIR / "twitter_accounts.db"
    if not accounts_db.exists():
        print("[INFO] No Twitter accounts configured, skipping Twitter collection.")
        print("[INFO] To enable: python3 -c \"from twscrape import API; ...\" (see README)")
        return items

    try:
        from twscrape import API, gather
        api = API(str(accounts_db))
        for acct in config.get("twitter_accounts", []):
            try:
                tweets = await gather(api.user_tweets(acct["handle"], limit=5))
                for tw in tweets:
                    h = hash_item("twitter", acct["handle"], str(tw.id))
                    if is_seen(conn, h):
                        continue
                    items.append({
                        "source": f"𝕏 {acct['name']} (@{acct['handle']})",
                        "type": "tweet",
                        "title": "",
                        "link": f"https://x.com/{acct['handle']}/status/{tw.id}",
                        "summary": tw.rawContent[:500] if tw.rawContent else "",
                    })
                    mark_seen(conn, h, f"twitter:{acct['handle']}", str(tw.id))
            except Exception as e:
                print(f"[WARN] Twitter fetch failed for @{acct['handle']}: {e}")
    except Exception as e:
        print(f"[WARN] twscrape error: {e}")
    return items


def cleanup_db(conn, days=30):
    cutoff = time.time() - days * 86400
    conn.execute("DELETE FROM seen WHERE ts < ?", (cutoff,))
    conn.commit()


async def main():
    config = json.loads(CONFIG_PATH.read_text())
    conn = init_db()

    lookback = config.get("lookback_hours", 26)
    cutoff_ts = time.time() - lookback * 3600

    print(f"[INFO] Collecting updates (lookback {lookback}h)...")

    rss_items = collect_rss(config, conn, cutoff_ts)
    twitter_items = await collect_twitter(config, conn)

    all_items = rss_items + twitter_items

    result = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total": len(all_items),
        "rss_count": len(rss_items),
        "twitter_count": len(twitter_items),
        "items": all_items,
    }

    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[OK] Collected {len(all_items)} new items → {OUTPUT_PATH}")

    cleanup_db(conn)
    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
