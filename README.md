# manual-scrobble
Manually Scrobble a Plex album to multi-scrobbler

# Download

Grab the latest build from the [Releases page](https://github.com/jspeyside/manual-scrobble/releases) —
no Python install required. Both read `PLEX_URL`/`PLEX_TOKEN`/`MS_URL`/`MS_TOKEN`
from the environment or a `.env` file placed next to the binary — see below.

**Windows** (`manual-scrobble-vX.Y.Z-windows.exe`) — opens a native window.
It's unsigned, so SmartScreen will show an "unknown publisher" warning the
first time you run it; click "More info" then "Run anyway".

**Linux** (`manual-scrobble-vX.Y.Z-linux`) — opens in your default browser
instead of a native window (it doesn't bundle Qt, so there's no windowing
toolkit available; see [gui.py](gui.py)'s native-mode comment for why). Mark
it executable after downloading — GitHub Releases don't reliably preserve
that bit:

```
chmod +x manual-scrobble-vX.Y.Z-linux
./manual-scrobble-vX.Y.Z-linux
```

# Directions
How it works and the two things you need:
Environment variables (can be set in the shell or in a `.env` file next to `scrobble.py`):
- PLEX_TOKEN
- PLEX_URL
- MS_URL
- MS_TOKEN


`PLEX_TOKEN` - Plex token — grab your X-Plex-Token (sign into Plex web, open any item's XML via "Get Info → View XML", copy the token from the URL). The script queries /library/metadata/{key} and /library/metadata/{key}/children on your PMS. Store this as an environment variable PLEX_TOKEN

`PLEX_URL` - Needs to be the actual PMS API base — often the same host if it's reverse-proxied, otherwise the direct server address.

`MS_URL` - The submit-listens endpoint of your multi-scrobbler instance, e.g. `https://your-scrobbler-host/1/submit-listens`.

`MS_TOKEN` - Multi-scrobbler token — Your multi-scrobbler must be configured to accept scrobbles from outside applications as if it were a Listenbrainz server. See https://docs.multi-scrobbler.app/configuration/sources/listenbrainz-endpoint/ for how to configure this. 

# GUI

`gui.py` provides a desktop window (built with [NiceGUI](https://nicegui.io)) for
the same workflow: paste an album URL/rating key, preview the cover art and
tracklist, then submit.

Prerequisites for the native window (Linux/WSL2, Qt backend):

```
sudo apt install libxcb-cursor0 libglu1-mesa
```

Then:

```
pipenv install
pipenv run gui              # opens a native window
pipenv run gui --no-native  # opens in a browser tab instead
```

The connection settings panel is prefilled from the same environment variables
as the CLI (PLEX_URL, PLEX_TOKEN, MS_URL, MS_TOKEN) and can be edited in the UI
for the session.

# Building the Windows .exe locally

PyInstaller builds a platform-native binary, so this only works run from an
actual Windows Python (not this repo's Linux/WSL2 dev setup):

```powershell
pip install pipenv
pipenv install --dev
pipenv run pyinstaller --noconfirm manual-scrobble.spec
```

The result is `dist\manual-scrobble.exe`. Always build from
[manual-scrobble.spec](manual-scrobble.spec) — not a hand-typed `pyinstaller`/
`nicegui-pack` command — since it's what keeps `PySide6`/`qtpy` (installed for
the Linux dev fallback, see the comment in [Pipfile](Pipfile)) out of the
Windows build. Skipping it silently produces a ~250MB exe with all of Qt
bundled instead of the normal ~70MB.

