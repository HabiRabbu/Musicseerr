from dataclasses import dataclass


@dataclass
class ListenBrainzArtist:
    artist_name: str
    listen_count: int
    artist_mbids: list[str] | None = None


@dataclass
class ListenBrainzReleaseGroup:
    release_group_name: str
    artist_name: str
    listen_count: int
    release_group_mbid: str | None = None
    artist_mbids: list[str] | None = None
    caa_id: int | None = None
    caa_release_mbid: str | None = None


@dataclass
class ListenBrainzRecording:
    track_name: str
    artist_name: str
    listen_count: int
    recording_mbid: str | None = None
    release_name: str | None = None
    release_mbid: str | None = None
    artist_mbids: list[str] | None = None


@dataclass
class ListenBrainzListen:
    track_name: str
    artist_name: str
    listened_at: int
    recording_mbid: str | None = None
    release_name: str | None = None
    release_mbid: str | None = None


@dataclass
class ListenBrainzGenreActivity:
    genre: str
    listen_count: int
    hour: int | None = None


@dataclass
class ListenBrainzSimilarArtist:
    artist_mbid: str
    artist_name: str
    listen_count: int
    score: float | None = None


ALLOWED_STATS_RANGE = [
    "this_week", "this_month", "this_year",
    "week", "month", "quarter", "year", "half_yearly", "all_time"
]


def parse_artist(item: dict) -> ListenBrainzArtist:
    mbid = item.get("artist_mbid")
    mbids = [mbid] if mbid else item.get("artist_mbids")
    return ListenBrainzArtist(
        artist_name=item.get("artist_name", "Unknown"),
        listen_count=item.get("listen_count", 0),
        artist_mbids=mbids,
    )


def parse_release_group(item: dict) -> ListenBrainzReleaseGroup:
    return ListenBrainzReleaseGroup(
        release_group_name=item.get("release_group_name", "Unknown"),
        artist_name=item.get("artist_name", "Unknown"),
        listen_count=item.get("listen_count", 0),
        release_group_mbid=item.get("release_group_mbid"),
        artist_mbids=item.get("artist_mbids"),
        caa_id=item.get("caa_id"),
        caa_release_mbid=item.get("caa_release_mbid"),
    )


def parse_recording(item: dict) -> ListenBrainzRecording:
    return ListenBrainzRecording(
        track_name=item.get("track_name", "Unknown"),
        artist_name=item.get("artist_name", "Unknown"),
        listen_count=item.get("listen_count", 0),
        recording_mbid=item.get("recording_mbid"),
        release_name=item.get("release_name"),
        release_mbid=item.get("release_mbid"),
        artist_mbids=item.get("artist_mbids"),
    )


def parse_listen(item: dict) -> ListenBrainzListen:
    track_meta = item.get("track_metadata", {})
    additional = track_meta.get("additional_info", {})
    mbid_mapping = track_meta.get("mbid_mapping", {})
    return ListenBrainzListen(
        track_name=track_meta.get("track_name", "Unknown"),
        artist_name=track_meta.get("artist_name", "Unknown"),
        listened_at=item.get("listened_at", 0),
        recording_mbid=mbid_mapping.get("recording_mbid") or additional.get("recording_mbid"),
        release_name=track_meta.get("release_name"),
        release_mbid=mbid_mapping.get("release_mbid") or additional.get("release_mbid"),
    )


def parse_artist_recording(item: dict) -> ListenBrainzRecording:
    return ListenBrainzRecording(
        track_name=item.get("recording_name", "Unknown"),
        artist_name=item.get("artist_name", "Unknown"),
        listen_count=item.get("total_listen_count", 0),
        recording_mbid=item.get("recording_mbid"),
        release_name=item.get("release_name"),
        release_mbid=item.get("release_mbid"),
        artist_mbids=item.get("artist_mbids"),
    )


def parse_similar_artist(artist_mbid: str, recordings: list[dict]) -> ListenBrainzSimilarArtist:
    if not recordings:
        return ListenBrainzSimilarArtist(
            artist_mbid=artist_mbid,
            artist_name="Unknown",
            listen_count=0,
        )
    first = recordings[0]
    total_count = sum(r.get("total_listen_count", 0) for r in recordings)
    return ListenBrainzSimilarArtist(
        artist_mbid=artist_mbid,
        artist_name=first.get("similar_artist_name", "Unknown"),
        listen_count=total_count,
    )
