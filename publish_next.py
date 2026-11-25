"""Publish the next queued Ranked Earth Reel to Instagram (@rankedearth.8).

    python3 publish_next.py            # publish the next "queued" post in queue.json, then commit + push the queue
    python3 publish_next.py --dry-run  # only show what would be published

Standard library only. The access token is NOT in this repo: the session's network proxy adds it to every
request to graph.facebook.com. Videos are served to Instagram from this public repo (raw.githubusercontent.com).
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://graph.facebook.com/v21.0"


def req(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} from {url.split('?')[0]}: {e.read()[:500].decode(errors='replace')}")


def git(*args):
    subprocess.run(["git", "-C", str(HERE), *args], check=True)


def main(dry=False):
    q = json.loads((HERE / "queue.json").read_text())
    nxt = next((p for p in q["posts"] if p["status"] == "queued"), None)
    if not nxt:
        print("QUEUE EMPTY: nothing to publish")
        return
    print("next:", nxt["slug"], "-", nxt["title"])
    if dry:
        print(nxt["caption"])
        return
    url = f"{q['raw_base']}/{nxt['video']}"
    c = req(f"{API}/{q['ig_user']}/media", {"media_type": "REELS", "video_url": url, "caption": nxt["caption"],
                                             "share_to_feed": "true", "thumb_offset": str(nxt.get("thumb_offset_ms", 1600))})
    cid = c["id"]
    for _ in range(90):
        st = req(f"{API}/{cid}?fields=status_code,status")
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"processing failed: {st}")
        time.sleep(10)
    else:
        raise SystemExit("still processing after 15 minutes")
    r = req(f"{API}/{q['ig_user']}/media_publish", {"creation_id": cid})
    info = req(f"{API}/{r['id']}?fields=permalink,timestamp")
    nxt.update(status="published", media_id=r["id"], permalink=info.get("permalink"),
               published_at=info.get("timestamp"), via="api")
    (HERE / "queue.json").write_text(json.dumps(q, indent=2, ensure_ascii=False))
    print("PUBLISHED:", nxt["title"], info.get("permalink"))
    left = sum(p["status"] == "queued" for p in q["posts"])
    print("queued posts left:", left)
    git("add", "queue.json")
    git("commit", "-m", f"Published {nxt['slug']} to Instagram\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
        "Claude-Session: https://claude.ai/code/session_01SFBNwfSFFKFonyZ1otcnA3")
    git("-c", "push.negotiate=true", "push", "origin", "HEAD")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
