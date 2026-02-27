from repositories.musicbrainz_base import build_musicbrainz_tag_query


def test_build_musicbrainz_tag_query_quotes_multiword_tag() -> None:
    query = build_musicbrainz_tag_query('Hip Hop')

    assert 'tag:"hip hop"^3' in query
    assert 'tag:"hip-hop"^2' in query
    assert 'tag:hip hop' not in query


def test_build_musicbrainz_tag_query_includes_standard_ampersand_aliases() -> None:
    query = build_musicbrainz_tag_query('R&B')

    assert 'tag:"r&b"^3' in query
    assert 'tag:"r and b"^2' in query
    assert 'tag:"r b"^2' in query


def test_build_musicbrainz_tag_query_escapes_lucene_phrase_chars() -> None:
    query = build_musicbrainz_tag_query('Drum "N" Bass')

    assert 'tag:"drum \\"n\\" bass"^3' in query


def test_build_musicbrainz_tag_query_deduplicates_variants() -> None:
    query = build_musicbrainz_tag_query('hip-hop')

    assert query.count('tag:"hip-hop"') == 1
    assert query.count('tag:"hip hop"') == 1
