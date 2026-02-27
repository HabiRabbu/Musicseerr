import pytest

from infrastructure.validators import clean_lastfm_bio, strip_html_tags


def test_strip_html_tags_removes_bold():
    assert strip_html_tags("<b>bold</b> text") == "bold text"


def test_strip_html_tags_removes_links():
    result = strip_html_tags('Visit <a href="https://example.com">example</a> site')
    assert result == "Visit example site"


def test_strip_html_tags_converts_br_to_newline():
    assert strip_html_tags("line one<br>line two") == "line one\nline two"
    assert strip_html_tags("line one<br/>line two") == "line one\nline two"


def test_strip_html_tags_converts_p_end_to_double_newline():
    result = strip_html_tags("<p>First paragraph</p><p>Second paragraph</p>")
    assert "First paragraph" in result
    assert "Second paragraph" in result
    assert "\n\n" in result


def test_strip_html_tags_handles_empty_string():
    assert strip_html_tags("") == ""


def test_strip_html_tags_handles_none():
    assert strip_html_tags(None) == ""


def test_strip_html_tags_handles_plain_text():
    assert strip_html_tags("just plain text") == "just plain text"


def test_strip_html_tags_handles_html_entities():
    assert strip_html_tags("rock &amp; roll") == "rock & roll"


def test_strip_html_tags_complex_html():
    html = (
        '<p>Radiohead are an English <b>rock</b> band from '
        '<a href="#">Abingdon</a>, Oxfordshire.</p>'
    )
    result = strip_html_tags(html)
    assert "<" not in result
    assert ">" not in result
    assert "Radiohead are an English rock band from Abingdon, Oxfordshire." in result


# --- clean_lastfm_bio tests ---


def test_clean_lastfm_bio_strips_read_more_suffix():
    html = (
        "Walter Carl Becker was an American musician. "
        '<a href="https://www.last.fm/music/Steely+Dan">Read more on Last.fm</a>'
    )
    result = clean_lastfm_bio(html)
    assert "Read more on Last.fm" not in result
    assert result == "Walter Carl Becker was an American musician."


def test_clean_lastfm_bio_strips_plain_text_suffix():
    text = "Some artist bio. Read more on Last.fm"
    result = clean_lastfm_bio(text)
    assert result == "Some artist bio."


def test_clean_lastfm_bio_no_suffix():
    text = "A clean bio with no Last.fm link."
    assert clean_lastfm_bio(text) == text


def test_clean_lastfm_bio_empty():
    assert clean_lastfm_bio("") == ""
    assert clean_lastfm_bio(None) == ""
