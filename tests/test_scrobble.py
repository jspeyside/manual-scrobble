import pytest
import requests

from scrobble import _mbid, build_listens, fetch_album, plex_get, rating_key_from_arg, submit


class FakeResponse:
    def __init__(self, json_data=None, status_code=200, raise_exc=None):
        self._json = json_data
        self.status_code = status_code
        self._raise_exc = raise_exc

    def json(self):
        return self._json

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc


# ---------- rating_key_from_arg ----------

def test_rating_key_from_arg_bare_digits():
    assert rating_key_from_arg("31825") == "31825"


def test_rating_key_from_arg_full_url():
    url = "https://plex.example/manage/index.html#!/server/abc/details?key=%2Flibrary%2Fmetadata%2F31825"
    assert rating_key_from_arg(url) == "31825"


def test_rating_key_from_arg_trailing_slash_in_key():
    url = "https://plex.example/manage/index.html#!/server/abc/details?key=%2Flibrary%2Fmetadata%2F31825%2F"
    assert rating_key_from_arg(url) == "31825"


def test_rating_key_from_arg_invalid_raises():
    with pytest.raises(ValueError):
        rating_key_from_arg("not a valid target")


def test_rating_key_from_arg_no_key_in_query_raises():
    url = "https://plex.example/manage/index.html#!/server/abc/details?foo=bar"
    with pytest.raises(ValueError):
        rating_key_from_arg(url)


# ---------- _mbid ----------

def test_mbid_exact_typed_match():
    guids = [{"id": "mbid://release/REL"}]
    assert _mbid(guids, "release") == "REL"


def test_mbid_does_not_match_release_group_prefix():
    # Regression: "release" must not match "release-group".
    guids = [{"id": "mbid://release-group/GROUP"}, {"id": "mbid://release/REL"}]
    assert _mbid(guids, "release") == "REL"


def test_mbid_wrong_type_returns_none():
    # Regression: asking for a type that isn't present must not return a
    # malformed value from a differently-typed guid.
    guids = [{"id": "mbid://release/REL"}]
    assert _mbid(guids, "recording") is None


def test_mbid_bare_fallback():
    guids = [{"id": "mbid://BARE"}]
    assert _mbid(guids, "recording") == "BARE"


def test_mbid_typed_match_preferred_over_bare():
    guids = [{"id": "mbid://BARE"}, {"id": "mbid://recording/REC"}]
    assert _mbid(guids, "recording") == "REC"


def test_mbid_empty_or_none_guids():
    assert _mbid([], "release") is None
    assert _mbid(None, "release") is None


# ---------- build_listens ----------

def test_build_listens_contiguous_and_ends_at_finished_at():
    album = {"title": "Album", "parentTitle": "Artist", "Guid": []}
    tracks = [
        {"title": "T1", "index": 1, "duration": 180000},
        {"title": "T2", "index": 2, "duration": 200000},
        {"title": "T3", "index": 3, "duration": 220000},
    ]
    finished_at = 100000
    listens = build_listens(album, tracks, finished_at)

    total = 180 + 200 + 220
    assert [lz["listened_at"] for lz in listens] == [
        finished_at - total,
        finished_at - total + 180,
        finished_at - total + 180 + 200,
    ]
    assert listens[-1]["listened_at"] + 220 == finished_at
    assert [lz["track_metadata"]["track_name"] for lz in listens] == ["T1", "T2", "T3"]


def test_build_listens_missing_duration_falls_back_to_210s():
    album = {"title": "A", "parentTitle": "Artist", "Guid": []}
    tracks = [{"title": "T1", "index": 1}]
    listens = build_listens(album, tracks, 1000)
    assert listens[0]["listened_at"] == 1000 - 210


def test_build_listens_zero_duration_is_not_replaced_by_fallback():
    album = {"title": "A", "parentTitle": "Artist", "Guid": []}
    tracks = [{"title": "T1", "index": 1, "duration": 0}]
    listens = build_listens(album, tracks, 1000)
    assert listens[0]["listened_at"] == 1000
    assert "duration_ms" not in listens[0]["track_metadata"]["additional_info"]


@pytest.mark.parametrize(
    "track,expected_artist",
    [
        ({"title": "x", "originalTitle": "Orig", "grandparentTitle": "Grand"}, "Orig"),
        ({"title": "x", "grandparentTitle": "Grand"}, "Grand"),
        ({"title": "x"}, "Artist"),
    ],
)
def test_build_listens_artist_fallback_chain(track, expected_artist):
    album = {"title": "A", "parentTitle": "Artist", "Guid": []}
    listens = build_listens(album, [track], 1000)
    assert listens[0]["track_metadata"]["artist_name"] == expected_artist


def test_build_listens_includes_mbids_when_present():
    album = {"title": "A", "parentTitle": "Artist", "Guid": [{"id": "mbid://release/REL"}]}
    tracks = [{"title": "T1", "index": 1, "Guid": [{"id": "mbid://recording/REC"}]}]
    info = build_listens(album, tracks, 1000)[0]["track_metadata"]["additional_info"]
    assert info["release_mbid"] == "REL"
    assert info["recording_mbid"] == "REC"


def test_build_listens_omits_mbids_when_absent():
    album = {"title": "A", "parentTitle": "Artist", "Guid": []}
    tracks = [{"title": "T1", "index": 1}]
    info = build_listens(album, tracks, 1000)[0]["track_metadata"]["additional_info"]
    assert "release_mbid" not in info
    assert "recording_mbid" not in info


def test_build_listens_empty_tracks_returns_empty_list():
    album = {"title": "A", "parentTitle": "Artist", "Guid": []}
    assert build_listens(album, [], 1000) == []


# ---------- plex_get / fetch_album ----------

def test_plex_get_url_and_headers(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured.update(url=url, headers=headers, timeout=timeout)
        return FakeResponse({"MediaContainer": {"ok": True}})

    monkeypatch.setattr("scrobble.requests.get", fake_get)
    result = plex_get("https://plex.example/", "TOKEN", "/library/metadata/1")

    assert result == {"ok": True}
    assert captured["url"] == "https://plex.example/library/metadata/1"
    assert captured["headers"]["X-Plex-Token"] == "TOKEN"
    assert captured["headers"]["Accept"] == "application/json"


def test_fetch_album(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/children"):
            return FakeResponse({"MediaContainer": {"Metadata": [{"title": "T1"}, {"title": "T2"}]}})
        return FakeResponse({"MediaContainer": {"Metadata": [{"type": "album", "title": "A"}]}})

    monkeypatch.setattr("scrobble.requests.get", fake_get)
    album, tracks = fetch_album("https://plex.example", "TOKEN", "31825")

    assert album == {"type": "album", "title": "A"}
    assert tracks == [{"title": "T1"}, {"title": "T2"}]


def test_fetch_album_raises_when_not_an_album(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        return FakeResponse({"MediaContainer": {"Metadata": [{"type": "track"}]}})

    monkeypatch.setattr("scrobble.requests.get", fake_get)
    with pytest.raises(ValueError):
        fetch_album("https://plex.example", "TOKEN", "1")


def test_fetch_album_no_children_metadata_returns_empty_list(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/children"):
            return FakeResponse({"MediaContainer": {}})
        return FakeResponse({"MediaContainer": {"Metadata": [{"type": "album"}]}})

    monkeypatch.setattr("scrobble.requests.get", fake_get)
    _, tracks = fetch_album("https://plex.example", "TOKEN", "1")
    assert tracks == []


# ---------- submit ----------

def test_submit_payload_and_headers(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResponse(status_code=200)

    monkeypatch.setattr("scrobble.requests.post", fake_post)
    listens = [{"listened_at": 1, "track_metadata": {}}]
    resp = submit("https://ms.example/1/submit-listens", "TOK", listens)

    assert resp.status_code == 200
    assert captured["url"] == "https://ms.example/1/submit-listens"
    assert captured["headers"]["Authorization"] == "Token TOK"
    assert captured["json"] == {"listen_type": "import", "payload": listens}


def test_submit_raises_for_status(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(status_code=500, raise_exc=requests.HTTPError("boom"))

    monkeypatch.setattr("scrobble.requests.post", fake_post)
    with pytest.raises(requests.HTTPError):
        submit("https://ms.example", "TOK", [])
