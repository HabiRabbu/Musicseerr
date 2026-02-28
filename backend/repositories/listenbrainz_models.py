import msgspec


class ListenBrainzArtist(msgspec.Struct):
    artist_name: str
    listen_count: int
    artist_mbids: list[str] | None = None


class ListenBrainzReleaseGroup(msgspec.Struct):
    release_group_name: str
    artist_name: str
    listen_count: int
    release_group_mbid: str | None = None
    artist_mbids: list[str] | None = None
    caa_release_mbid: str | None = None
    caa_id: int | None = None


class ListenBrainzRecording(msgspec.Struct):
    track_name: str
    artist_name: str
    listen_count: int
    recording_mbid: str | None = None
    release_name: str | None = None
    release_mbid: str | None = None
    artist_mbids: list[str] | None = None


class ListenBrainzListen(msgspec.Struct):
    track_name: str
    artist_name: str
    listened_at: int
    recording_mbid: str | None = None
    release_name: str | None = None
    release_mbid: str | None = None
    artist_mbids: list[str] | None = None


class ListenBrainzGenreActivity(msgspec.Struct):
    genre: str
    listen_count: int
    hour: int | None = None


class ListenBrainzSimilarArtist(msgspec.Struct):
    artist_mbid: str
    artist_name: str
    listen_count: int
    score: float | None = None


class ListenBrainzFeedbackRecording(msgspec.Struct):
    track_name: str
    artist_name: str
    release_name: str | None = None
    recording_mbid: str | None = None
    release_mbid: str | None = None
    artist_mbids: list[str] | None = None
    score: int = 0


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
        artist_mbids=mbid_mapping.get("artist_mbids"),
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


def parse_feedback_recording(item: dict) -> ListenBrainzFeedbackRecording:
    metadata = item.get("recording_metadata") or item.get("track_metadata") or item.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    mbid_mapping = metadata.get("mbid_mapping", {})
    if not isinstance(mbid_mapping, dict):
        mbid_mapping = {}

    artist_mbids = mbid_mapping.get("artist_mbids") or metadata.get("artist_mbids")
    if artist_mbids is None and metadata.get("artist_mbid"):
        artist_mbids = [metadata.get("artist_mbid")]

    return ListenBrainzFeedbackRecording(
        track_name=(
            metadata.get("track_name")
            or metadata.get("recording_name")
            or item.get("track_name")
            or "Unknown"
        ),
        artist_name=(
            metadata.get("artist_name")
            or metadata.get("artist")
            or item.get("artist_name")
            or "Unknown"
        ),
        release_name=(
            metadata.get("release_name")
            or metadata.get("album_name")
            or item.get("release_name")
        ),
        recording_mbid=item.get("recording_mbid") or mbid_mapping.get("recording_mbid") or metadata.get("recording_mbid"),
        release_mbid=mbid_mapping.get("release_mbid") or item.get("release_mbid") or metadata.get("release_mbid"),
        artist_mbids=artist_mbids,
        score=int(item.get("score", 0) or 0),
    )
