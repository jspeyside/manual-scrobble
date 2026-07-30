# manual-scrobble
Manually Scrobble a Plex album to multi-scrobbler

# Directions
How it works and the two things you need:
Environment variables (can be set in the shell or in a `.env` file next to `scrobble.py`):
- PLEX_TOKEN
- PLEX_URL
- MS_URL
- MS_TOKEN


PLEX_TOKEN - Plex token — grab your X-Plex-Token (sign into Plex web, open any item's XML via "Get Info → View XML", copy the token from the URL). The script queries /library/metadata/{key} and /library/metadata/{key}/children on your PMS. Store this as an environment variable PLEX_TOKEN

PLEX_URL - Needs to be the actual PMS API base — often the same host if it's reverse-proxied, otherwise the direct server address.

MS_URL - The submit-listens endpoint of your multi-scrobbler instance, e.g. `https://your-scrobbler-host/1/submit-listens`.

MS_TOKEN - Multi-scrobbler token — Your multi-scrobbler must be configured to accept scrobbles from outside applications as if it were a Listenbrainz server. See https://docs.multi-scrobbler.app/configuration/sources/listenbrainz-endpoint/ for how to configure this. 

