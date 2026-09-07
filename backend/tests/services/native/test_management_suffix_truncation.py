"""Regression tests for suffix-preserving component truncation.

Covers the fix for the AudioWriteError cluster caused by
``_clean_management_component`` trimming the file extension when a
management path component exceeds ``maximum_component_length``.

The real-world failure surface: a destination basename like
``..._01_Symphony no. 35 ..._ I. Allegro con spirito.flac`` (>= 240 UTF-8
bytes) was truncated blindly on the decode boundary, mangling the suffix
into something like ``. Allegro con spir`` so the staged artifact was not
recognised as an admitted audio format.
"""

from pathlib import Path

import pytest

from api.v1.schemas.library_management import PathCompatibilitySettings
from services.native.naming import NamingTemplateEngine


def _compat(**overrides) -> PathCompatibilitySettings:
    base = dict(
        windows_compatible=True,
        replace_non_ascii=False,
        replace_spaces_with_underscores=False,
        separator_replacement="_",
        maximum_component_length=240,
        maximum_path_length=4096,
        unicode_normalization="NFC",
        extension_case="preserve",
        windows_legacy_path_limit=False,
    )
    base.update(overrides)
    return PathCompatibilitySettings(**base)


def _literal_artist_dir() -> str:
    # Directory component: must never be treated as a file extension even
    # when it contains dots (e.g. "Symphony no. 2 ...").
    return "Gustav Mahler - Symphony no. 2 “Resurrection”"


@pytest.fixture
def engine() -> NamingTemplateEngine:
    return NamingTemplateEngine()


def _name(result) -> str:
    return result.relative_path.rsplit("/", 1)[-1]


def test_short_filename_unchanged(engine) -> None:
    compat = _compat()
    result = engine.format_management_literal_path(
        f"{_literal_artist_dir()}/A Short Title.flac", compat
    )
    assert result.relative_path == (
        f"{_literal_artist_dir()}/A Short Title.flac"
    )


def test_flac_over_240_bytes_keeps_suffix(engine) -> None:
    stem = "Symphony no. 35 in D major, K. 385 Haffner - I. Allegro con spirito"
    # inflate so the full name clearly exceeds 240 UTF-8 bytes
    inflated = (stem + " ") * 4 + stem
    name = f"{inflated}.flac"
    assert len(name.encode("utf-8")) > 240
    result = engine.format_management_literal_path(
        f"{_literal_artist_dir()}/{name}", _compat()
    )
    out_name = _name(result)
    assert len(out_name.encode("utf-8")) <= 240
    assert out_name.endswith(".flac")
    assert Path(out_name).suffix == ".flac"
    assert not out_name.endswith(". Allegro")


def test_flac_internal_dots_never_used_as_suffix(engine) -> None:
    stem = "Symphony no. 35 in D major, K. 385 Haffner - I. Allegro con spirito"
    inflated = (stem + " ") * 4 + stem
    name = f"{inflated}.flac"
    result = engine.format_management_literal_path(
        f"{_literal_artist_dir()}/{name}", _compat()
    )
    out_name = _name(result)
    assert Path(out_name).suffix == ".flac"
    # the naive pre-fix path used ". Allegro con spir"; guarantee it is gone
    assert not out_name.split(".flac")[0].endswith(". Allegro con spir")


def test_utf8_multibyte_preserved_and_valid(engine) -> None:
    # ó ü – etc. must survive truncation; output must be <= 240 bytes, valid
    # UTF-8, and keep ".flac".
    long_title = (
        "Ópera – Variaciones sobre un tema de Paganini, op. 38 "
        "– Estudio nº 12 “Le Streghe” – Scherzo en si bemol mayor – "
        "Rapsodia española – La Campanella – Mephisto Waltz"
    )
    inflated = (long_title + " ") * 3 + long_title
    name = f"{inflated}.flac"
    assert len(name.encode("utf-8")) > 240
    result = engine.format_management_literal_path(
        f"{_literal_artist_dir()}/{name}", _compat()
    )
    out_name = _name(result)
    out_bytes = out_name.encode("utf-8")
    assert len(out_bytes) <= 240
    out_bytes.decode("utf-8")  # must be valid UTF-8, raises otherwise
    assert out_name.endswith(".flac")


def test_long_internal_directory_with_dots_keeps_dot_contents(engine) -> None:
    # Intermediate dir with lots of dots must NOT be treated as an extension
    # nor get its own suffix preserved logic applied.
    compat = _compat(maximum_component_length=60)
    dir_name = "Gustav Mahler - Symphony no. 2 “Resurrection” - Live in Vienna"
    result = engine.format_management_literal_path(
        f"{dir_name}/track.flac", compat
    )
    first = result.relative_path.split("/")[0]
    assert len(first.encode("utf-8")) <= 60
    assert Path(result.relative_path).name == "track.flac"


@pytest.mark.parametrize(
    "extension",
    [".mp3", ".m4a", ".opus", ".ogg", ".wav"],
)
def test_other_audio_extensions_preserved(engine, extension) -> None:
    stem = "A rather long track title that keeps going and going"
    inflated = (stem + " ") * 5 + stem
    name = f"{inflated}{extension}"
    assert len(name.encode("utf-8")) > 240
    result = engine.format_management_literal_path(
        f"{_literal_artist_dir()}/{name}", _compat()
    )
    out_name = _name(result)
    assert len(out_name.encode("utf-8")) <= 240
    assert out_name.endswith(extension)


def test_literal_sidecar_lrc_preserved(engine) -> None:
    stem = (
        "Assassin's Creed Valhalla - Some impossibly long lyrical track name "
        "that is designed to blow way past the component limit and overflow"
    )
    inflated = (stem + " ") * 3 + stem
    name = f"{inflated}.lrc"
    assert len(name.encode("utf-8")) > 240
    result = engine.format_management_literal_path(
        f"{_literal_artist_dir()}/{name}", _compat()
    )
    out_name = _name(result)
    assert len(out_name.encode("utf-8")) <= 240
    assert out_name.endswith(".lrc")


def test_literal_sidecar_jpg_preserved(engine) -> None:
    name = f"{'x' * 250}.jpg"
    result = engine.format_management_literal_path(
        f"Artist/Album ({2020})/{name}", _compat()
    )
    out_name = _name(result)
    assert len(out_name.encode("utf-8")) <= 240
    assert out_name.endswith(".jpg")


def test_boundary_exact_240_untouched(engine) -> None:
    # At exactly the limit there is no truncation at all.
    name = "a" * 235 + ".flac"  # 235 + 5 = 240 bytes
    assert len(name.encode("utf-8")) == 240
    result = engine.format_management_literal_path(
        f"Artist/{name}", _compat()
    )
    assert _name(result) == name
    assert len(_name(result).encode("utf-8")) == 240


def test_just_over_240_truncates_stem_not_suffix(engine) -> None:
    # 241 bytes total: the stem is trimmed, the ".flac" suffix is kept.
    name = "a" * 236 + ".flac"  # 241 bytes
    assert len(name.encode("utf-8")) == 241
    result = engine.format_management_literal_path(
        f"Artist/{name}", _compat()
    )
    out_name = _name(result)
    assert len(out_name.encode("utf-8")) == 240
    assert out_name.endswith(".flac")