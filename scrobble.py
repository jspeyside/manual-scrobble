#!/usr/bin/env python3
"""
Manually scrobble a whole Plex album to a multi-scrobbler (ListenBrainz endpoint) instance.

Usage:
    export PLEX_URL="https://<plex-server>"      # base URL of your PMS
    export PLEX_TOKEN="xxxxxxxxxxxxxxxxxxxx"           # X-Plex-Token
    export MS_URL="https://<scrobbler-url>/1/submit-listens"
    export MS_TOKEN="your-multi-scrobbler-lz-token"    # token configured on the LZ endpoint source

    # or place the same variables in a .env file next to this script

    python scrobble_album.py "https://<plex-server>/manage/index.html#!/server/45f5.../details?key=%2Flibrary%2Fmetadata%2F31825"

    # or pass the rating key directly:
    python scrobble_album.py 31825

Options:
    --finished-at "2026-07-30 21:00"   # when the listen ended (default: now)
    --dry-run                          # print payload, don't submit
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

import requests
from dotenv import load_dotenv

# python-dotenv's default load_dotenv() looks for .env by walking up from the
# current working directory, which is unreliable for a packaged .exe — the
# CWD at launch depends on how it was started (double-click, shortcut, etc.),
# not where the .exe file actually lives. Resolve explicitly instead, so a
# .env next to the .exe (or next to this script, when run from source) is
# always found regardless of the launch CWD.
_app_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
load_dotenv(_app_dir / ".env")


# ---------- Plex URL parsing ----------

def rating_key_from_arg(arg: str) -> str:
    """Accept a bare rating key (31825) or a full Plex web URL and return the rating key."""
    if arg.isdigit():
        return arg

    # The interesting bits live in the hash fragment: #!/server/<id>/details?key=%2Flibrary%2Fmetadata%2F31825
    frag = urlparse(arg).fragment
    if "?" in frag:
        query = frag.split("?", 1)[1]
        key = parse_qs(query).get("key", [None])[0]
        if key:
            key = unquote(key)                 # -> /library/metadata/31825
            return key.rstrip("/").split("/")[-1]

    raise ValueError(f"Could not extract a rating key from: {arg}")


# ---------- Plex API ----------

def plex_get(base: str, token: str, path: str) -> dict:
    r = requests.get(
        f"{base.rstrip('/')}{path}",
        headers={"X-Plex-Token": token, "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["MediaContainer"]


def _mbid(guids, prefix):
    """Extract a MusicBrainz id of a given type from a Plex Guid list."""
    bare = None
    for g in guids or []:
        gid = g.get("id", "")
        if not gid.startswith("mbid://"):
            continue
        rest = gid[len("mbid://"):]
        if rest.startswith(f"{prefix}/"):
            return rest[len(prefix) + 1:]
        if "/" not in rest and bare is None:
            bare = rest  # some agents store a bare mbid
    return bare


def fetch_album(base: str, token: str, rating_key: str):
    album = plex_get(base, token, f"/library/metadata/{rating_key}")["Metadata"][0]
    if album.get("type") != "album":
        raise ValueError(f"Rating key {rating_key} is a '{album.get('type')}', not an album.")

    children = plex_get(base, token, f"/library/metadata/{rating_key}/children")
    tracks = children.get("Metadata", [])
    return album, tracks


# ---------- ListenBrainz payload ----------

def build_listens(album: dict, tracks: list, finished_at: int) -> list:
    """
    Build ListenBrainz listens spaced by track duration, ending at `finished_at`,
    so the album reads as a real front-to-back listen.
    """
    album_name = album.get("title")
    album_artist = album.get("parentTitle")  # artist of the album
    release_mbid = _mbid(album.get("Guid"), "release")

    # Durations in seconds; fall back to 3.5 min if Plex has none.
    durations = [int(t.get("duration", 210000)) // 1000 for t in tracks]
    total = sum(durations)
    start = finished_at - total

    listens = []
    offset = 0
    for t, dur in zip(tracks, durations):
        artist = t.get("originalTitle") or t.get("grandparentTitle") or album_artist
        additional = {
            "duration_ms": int(t.get("duration", 0)) or None,
            "tracknumber": t.get("index"),
            "media_player": "plex-manual-scrobble",
            "submission_client": "scrobble_album.py",
        }
        recording_mbid = _mbid(t.get("Guid"), "recording")
        if recording_mbid:
            additional["recording_mbid"] = recording_mbid
        if release_mbid:
            additional["release_mbid"] = release_mbid
        additional = {k: v for k, v in additional.items() if v is not None}

        listens.append({
            "listened_at": start + offset,
            "track_metadata": {
                "artist_name": artist,
                "track_name": t.get("title"),
                "release_name": album_name,
                "additional_info": additional,
            },
        })
        offset += dur

    return listens


def submit(ms_url: str, ms_token: str, listens: list):
    payload = {"listen_type": "import", "payload": listens}
    r = requests.post(
        ms_url,
        headers={"Authorization": f"Token {ms_token}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Scrobble a Plex album to multi-scrobbler.")
    ap.add_argument("target", help="Plex web URL or bare rating key")
    ap.add_argument("--finished-at", help='When the listen ended, e.g. "2026-07-30 21:00" (default: now)')
    ap.add_argument("--dry-run", action="store_true", help="Print payload without submitting")
    args = ap.parse_args()

    plex_url = os.environ["PLEX_URL"]
    plex_token = os.environ["PLEX_TOKEN"]
    ms_url = os.environ["MS_URL"]
    ms_token = os.environ.get("MS_TOKEN", "")

    if args.finished_at:
        finished_at = int(datetime.fromisoformat(args.finished_at).timestamp())
    else:
        finished_at = int(time.time())

    rating_key = rating_key_from_arg(args.target)
    album, tracks = fetch_album(plex_url, plex_token, rating_key)
    if not tracks:
        sys.exit("No tracks found for that album.")

    listens = build_listens(album, tracks, finished_at)

    print(f"Album : {album.get('parentTitle')} — {album.get('title')} ({len(tracks)} tracks)")
    for lz in listens:
        tm = lz["track_metadata"]
        ts = datetime.fromtimestamp(lz["listened_at"]).strftime("%H:%M")
        print(f"  [{ts}] {tm['artist_name']} - {tm['track_name']}")

    if args.dry_run:
        import json
        print("\n--- payload ---")
        print(json.dumps({"listen_type": "import", "payload": listens}, indent=2))
        return

    if not ms_token:
        sys.exit("MS_TOKEN not set — required for the Authorization header.")

    resp = submit(ms_url, ms_token, listens)
    print(f"\nSubmitted {len(listens)} listens -> {resp.status_code}")


if __name__ == "__main__":
    main()
