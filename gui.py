#!/usr/bin/env python3
"""
NiceGUI front-end for scrobble.py.

Usage:
    pipenv run gui                 # opens a native desktop window
    pipenv run gui --no-native     # opens in a browser tab instead

Uses the same PLEX_URL / PLEX_TOKEN / MS_URL / MS_TOKEN as the CLI (from the
environment or a .env file), prefilled into an editable connection panel.
"""

import argparse
import os
import sys
from datetime import datetime

import requests
from nicegui import native, run, ui

from scrobble import build_listens, fetch_album, rating_key_from_arg, submit


def _format_time(ts: int) -> str:
    """12-hour clock without a leading zero, e.g. '8:40 PM'."""
    return datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")


def parse_finished_at(date_value: str, time_value: str) -> int:
    combined = f"{date_value} {time_value}"
    try:
        return int(datetime.strptime(combined, "%Y-%m-%d %I:%M %p").timestamp())
    except ValueError:
        raise ValueError("Enter date as YYYY-MM-DD and time as HH:MM AM/PM") from None


def select_tracks(tracks: list, selected_keys: set) -> list:
    """Filter tracks to the selected ratingKeys, preserving album order."""
    return [t for t in tracks if t.get("ratingKey") in selected_keys]


@ui.page("/")
def index():
    state = {"album": None, "tracks": None, "listens": None}

    with ui.column().classes("w-full max-w-3xl mx-auto gap-4 p-4"):
        ui.label("Manual Scrobble").classes("text-2xl font-bold")

        with ui.expansion("Connection settings", icon="settings").classes("w-full"):
            plex_url = ui.input("PLEX_URL", value=os.environ.get("PLEX_URL", "")).classes("w-full")
            plex_token = ui.input(
                "PLEX_TOKEN", value=os.environ.get("PLEX_TOKEN", ""), password=True, password_toggle_button=True
            ).classes("w-full")
            ms_url = ui.input("MS_URL", value=os.environ.get("MS_URL", "")).classes("w-full")
            ms_token = ui.input(
                "MS_TOKEN", value=os.environ.get("MS_TOKEN", ""), password=True, password_toggle_button=True
            ).classes("w-full")

        target = ui.input(
            "Plex album URL or rating key",
            placeholder='https://.../details?key=%2Flibrary%2Fmetadata%2F31825 or 31825',
        ).classes("w-full")

        with ui.expansion("Listen finished at", icon="schedule").classes("w-full") as finished_at_expansion:
            finished_at_expansion.tooltip("When the listen ended (default: now)")
            with ui.row().classes("items-center gap-4"):
                finished_at_date = ui.input("Date (YYYY-MM-DD)", value=datetime.now().strftime("%Y-%m-%d"))
                with finished_at_date.add_slot("append"):
                    date_icon = ui.icon("event").classes("cursor-pointer")
                with ui.menu() as date_menu:
                    ui.date().bind_value(finished_at_date)
                date_icon.on("click", date_menu.open)

                finished_at_time = ui.input("Time (HH:MM AM/PM)", value=datetime.now().strftime("%I:%M %p"))
                with finished_at_time.add_slot("append"):
                    time_icon = ui.icon("access_time").classes("cursor-pointer")
                with ui.menu() as time_menu:
                    ui.time(mask="hh:mm A").bind_value(finished_at_time)
                time_icon.on("click", time_menu.open)

        load_button = ui.button("Load / Preview")
        preview_card = ui.card().classes("w-full")
        preview_card.visible = False
        with preview_card:
            album_image = ui.image().classes("w-32 h-32 object-cover").props("no-spinner")
            album_image.visible = False
            album_label = ui.label().classes("text-lg font-semibold")
            ui.label("Select the tracks to scrobble (all selected by default).").classes("text-sm text-gray-500")
            tracks_table = ui.table(
                columns=[
                    {"name": "index", "label": "#", "field": "index"},
                    {"name": "artist", "label": "Artist", "field": "artist"},
                    {"name": "title", "label": "Title", "field": "title"},
                    {"name": "time", "label": "Time", "field": "time"},
                ],
                rows=[],
                row_key="key",
                selection="multiple",
            ).classes("w-full")

        submit_button = ui.button("Submit", color="positive")
        submit_button.disable()

        def finished_at_timestamp() -> int:
            return parse_finished_at(finished_at_date.value, finished_at_time.value)

        def refresh_listens():
            """Recompute contiguous listen timestamps for the currently selected tracks."""
            if not state["tracks"]:
                return

            selected_keys = {row["key"] for row in tracks_table.selected}
            selected_tracks = select_tracks(state["tracks"], selected_keys)

            if not selected_tracks:
                state["listens"] = []
                for row in tracks_table.rows:
                    row["time"] = "—"
                tracks_table.update()
                submit_button.disable()
                submit_button.set_text("Submit")
                return

            try:
                listens = build_listens(state["album"], selected_tracks, finished_at_timestamp())
            except ValueError as e:
                ui.notify(str(e), type="negative")
                return

            state["listens"] = listens
            time_by_key = {
                t.get("ratingKey"): _format_time(lz["listened_at"])
                for t, lz in zip(selected_tracks, listens)
            }
            for row in tracks_table.rows:
                row["time"] = time_by_key.get(row["key"], "—")
            tracks_table.update()

            submit_button.enable()
            submit_button.set_text(f"Submit ({len(listens)} listens)")

        async def do_load():
            submit_button.disable()
            preview_card.visible = False
            load_button.disable()
            try:
                key = rating_key_from_arg(target.value.strip())
                album, tracks = await run.io_bound(fetch_album, plex_url.value, plex_token.value, key)
                if not tracks:
                    ui.notify("No tracks found for that album.", type="negative")
                    return

                listens = build_listens(album, tracks, finished_at_timestamp())
                state["album"], state["tracks"] = album, tracks

                thumb = album.get("thumb")
                if thumb:
                    album_image.set_source(f"{plex_url.value.rstrip('/')}{thumb}?X-Plex-Token={plex_token.value}")
                    album_image.visible = True
                else:
                    album_image.visible = False

                album_label.set_text(
                    f"{album.get('parentTitle')} — {album.get('title')} ({len(tracks)} tracks)"
                )
                tracks_table.rows = [
                    {
                        "key": t.get("ratingKey"),
                        "index": t.get("index"),
                        "artist": lz["track_metadata"]["artist_name"],
                        "title": lz["track_metadata"]["track_name"],
                        "time": _format_time(lz["listened_at"]),
                    }
                    for t, lz in zip(tracks, listens)
                ]
                tracks_table.selected = list(tracks_table.rows)
                preview_card.visible = True
                refresh_listens()
            except ValueError as e:
                ui.notify(str(e), type="negative")
            except requests.HTTPError as e:
                ui.notify(f"Plex request failed: {e}", type="negative")
            finally:
                load_button.enable()

        async def do_submit():
            if not state["listens"]:
                return
            if not ms_token.value:
                ui.notify("MS_TOKEN not set — required for the Authorization header.", type="negative")
                return
            submit_button.disable()
            try:
                resp = await run.io_bound(submit, ms_url.value, ms_token.value, state["listens"])
                ui.notify(f"Submitted {len(state['listens'])} listens -> {resp.status_code}", type="positive")
            except requests.HTTPError as e:
                ui.notify(f"Submit failed: {e}", type="negative")
            finally:
                submit_button.enable()

        load_button.on_click(do_load)
        submit_button.on_click(do_submit)
        tracks_table.on_select(lambda _: refresh_listens())
        finished_at_date.on_value_change(lambda _: refresh_listens())
        finished_at_time.on_value_change(lambda _: refresh_listens())


def main():
    ap = argparse.ArgumentParser(description="GUI for scrobbling a Plex album to multi-scrobbler.")
    # The frozen Linux binary excludes Qt/PySide6 (see manual-scrobble.spec) to
    # stay small, so it has no native webview backend available. Default to
    # browser mode there; every other case (from source, or the frozen Windows
    # exe, which uses the system WebView2 runtime) still defaults to native.
    default_native = not (getattr(sys, "frozen", False) and sys.platform.startswith("linux"))
    ap.add_argument("--native", dest="native", action="store_true", default=default_native)
    ap.add_argument("--no-native", dest="native", action="store_false", help="Open in a browser tab instead of a native window")
    args, _ = ap.parse_known_args()

    ui.run(
        native=args.native,
        title="Manual Scrobble",
        reload=False,
        port=native.find_open_port() if args.native else 8080,
        window_size=(900, 850) if args.native else None,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
