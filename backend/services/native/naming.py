"""NamingTemplateEngine - render a naming template into a filesystem path.

Substitutes ``{variable}`` (and ``{track:02d}`` style) tokens from an
``AudioTag`` into a relative ``Path``, then normalises each component: NFC
unicode form, invalid-filesystem-character replacement, and a 252-byte length
cap that never splits a multi-byte UTF-8 character.

Edition-suffix stripping is intentionally NOT here - it is a matcher concern
(``MusicBrainzMatcher``), applied before fuzzy matching, not to output paths.
"""

import re
import unicodedata
from pathlib import Path

from api.v1.schemas.library_management import (
    MANAGED_FIELD_NAMES,
    PathCompatibilitySettings,
)
from core.exceptions import PathLimitExceededError, ScriptValidationError
from core.management_script_language import (
    EvaluationBudget,
    ScriptValue,
    compile_naming_template,
    evaluate_expression,
    walk_expressions,
)
from models.audio import AudioTag
from models.audio_metadata import ReadAudioDocument
from models.library_management_scripts import NamingRenderResult
from models.library_management_planning import ManagementNamingContext

# Leaves a 3-byte margin under the common 255-byte filename limit so a final
# multi-byte character truncation never overflows.
_MAX_COMPONENT_BYTES = 252

# Windows reserved device names (case-insensitive, with or without extension).
# Disarmed even on Linux so a library copied to an SMB/Windows host stays valid.
_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)
_LEADING_THE = re.compile(r"^the\s+", re.IGNORECASE)


def _artist_initial(artist: str, normalization_form: str) -> str:
    """Return the single-code-point artist bucket for a naming template."""
    name = unicodedata.normalize(normalization_form, artist).strip()
    name = _LEADING_THE.sub("", name, count=1).strip()
    if not name:
        return "#"
    first = name[0]
    if not first.isalpha():
        return "#"
    return next(
        (character for character in first.upper() if character.isalpha()),
        "#",
    )


class NamingTemplateEngine:
    DEFAULT = "{albumartist}/{album} ({year})/{disc:02d}{track:02d} {title}.{ext}"

    # Plain variables (format specs ignored) and the two that honour ``:fmt``.
    _VARIABLES = frozenset(
        {
            "artist",
            "album",
            "albumartist",
            "initial",
            "year",
            "title",
            "ext",
            "musicbrainz_id",
            "artist_mbid",
            "genre",
            "medium",
        }
    )
    _FORMATTED = frozenset({"track", "disc"})

    _TOKEN = re.compile(r"(\{[^}]+\})")
    # FS-reserved chars plus all C0 control characters and DEL.
    _INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
    _ALWAYS_INVALID_VALUE_CHARS = re.compile(r"[/\\\x00-\x1f\x7f]")
    _MANAGEMENT_VARIABLES = frozenset(
        {
            *MANAGED_FIELD_NAMES,
            "genre",
            "genres",
            "primary_genre",
            "artist_display",
            "artists",
            "artist_sorts",
            "album_artist_display",
            "album_artists",
            "album_artist_sorts",
            "albumartist",
            "initial",
            "year",
            "track",
            "disc",
            "ext",
            "extension",
            "medium",
            "album_disambiguation",
            "medium_format",
            "medium_number",
            "musicbrainz_id",
            "artist_mbid",
            "codec",
            "quality",
            "bitrate",
            "sample_rate",
            "bit_depth",
            "artwork_type",
            "artwork_comment",
            "artwork_extension",
            "artwork_format",
        }
    )

    def format_path(self, template: str, tag: AudioTag, ext: str) -> Path:
        return self._normalize(self._render(template, tag, ext))

    def validate_template(self, template: str) -> list[str]:
        """Return human-readable errors for unknown variables / bad format specs."""
        errors: list[str] = []
        for segment in template.split("/"):
            if segment.strip() in ("..", "."):
                errors.append("Path segment '..' or '.' is not allowed")
        for part in self._TOKEN.split(template):
            if not (part.startswith("{") and part.endswith("}")):
                continue
            token = part[1:-1]
            var, _, fmt = token.partition(":")
            if var not in self._VARIABLES and var not in self._FORMATTED:
                errors.append(f"Unknown variable: {{{var}}}")
            elif fmt and var not in self._FORMATTED:
                errors.append(f"Variable {{{var}}} does not support a format spec")
        return errors

    def validate_management_script(
        self,
        source: str,
        *,
        script_name: str = "naming script",
    ) -> None:
        segments = compile_naming_template(source, script_name=script_name)
        if "\n" in source or "\r" in source:
            raise ScriptValidationError(
                "Naming scripts must be a single path template.",
                script_name=script_name,
                line=1,
                column=1,
            )
        if source.startswith("/"):
            raise ScriptValidationError(
                "Naming output must be relative.",
                script_name=script_name,
                line=1,
                column=1,
            )
        for segment in segments:
            if segment.legacy_variable is not None:
                variable = segment.legacy_variable
                if variable not in self._MANAGEMENT_VARIABLES:
                    raise ScriptValidationError(
                        f"Unknown naming variable: {variable}.",
                        script_name=script_name,
                        line=segment.line,
                        column=segment.column,
                    )
                if segment.format_spec and variable not in {
                    "track",
                    "disc",
                    "track_number",
                    "disc_number",
                    "total_tracks",
                    "total_discs",
                    "medium_number",
                }:
                    raise ScriptValidationError(
                        f"Variable {variable} does not support a numeric format.",
                        script_name=script_name,
                        line=segment.line,
                        column=segment.column,
                    )
            if segment.expression is not None:
                for expression in walk_expressions(segment.expression):
                    if (
                        expression.kind == "variable"
                        and expression.value not in self._MANAGEMENT_VARIABLES
                    ):
                        raise ScriptValidationError(
                            f"Unknown naming variable: {expression.value}.",
                            script_name=script_name,
                            line=expression.line,
                            column=expression.column,
                        )

    def format_management_path(
        self,
        source: str,
        document: ReadAudioDocument,
        compatibility: PathCompatibilitySettings,
        *,
        script_name: str = "naming script",
        root: Path | None = None,
        artwork_type: str = "",
        artwork_comment: str = "",
        artwork_extension: str = "",
        artwork_format: str = "",
        naming_context: ManagementNamingContext | None = None,
    ) -> NamingRenderResult:
        self.validate_management_script(source, script_name=script_name)
        variables = self._management_variables(
            document,
            compatibility,
            artwork_type=artwork_type,
            artwork_comment=artwork_comment,
            artwork_extension=artwork_extension,
            artwork_format=artwork_format,
            naming_context=naming_context,
        )
        budget = EvaluationBudget(script_name=script_name)
        rendered: list[str] = []
        for segment in compile_naming_template(source, script_name=script_name):
            if segment.literal is not None:
                rendered.append(segment.literal)
                continue
            if segment.legacy_variable is not None:
                value = variables.get(segment.legacy_variable)
                text = self._script_text(value)
                if segment.format_spec:
                    try:
                        text = format(int(text), segment.format_spec)
                    except (TypeError, ValueError) as error:
                        raise ScriptValidationError(
                            "Numeric naming format received a non-integer value.",
                            script_name=script_name,
                            line=segment.line,
                            column=segment.column,
                        ) from error
            else:
                value = evaluate_expression(segment.expression, variables, budget)
                text = self._script_text(value)
            rendered.append(
                self._sanitize_substituted_value(
                    text,
                    compatibility.separator_replacement,
                    compatibility.windows_compatible,
                )
            )
        raw_path = "".join(rendered)
        parts = raw_path.split("/")
        if (
            not raw_path
            or raw_path.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ScriptValidationError(
                "Naming script rendered an empty, absolute, or traversing path.",
                script_name=script_name,
                line=1,
                column=1,
            )
        cleaned = tuple(
            self._clean_management_component(
                part,
                compatibility,
                preserve_suffix=(index == len(parts) - 1),
            )
            for index, part in enumerate(parts)
        )
        relative = "/".join(cleaned)
        encoded_length = len(relative.encode("utf-8"))
        if encoded_length > compatibility.maximum_path_length:
            raise PathLimitExceededError(
                "Rendered relative path exceeds the configured path limit.",
                script_name=script_name,
                line=1,
                column=1,
            )
        absolute_text = str(root / Path(relative)) if root is not None else relative
        if len(absolute_text.encode("utf-8")) > compatibility.maximum_path_length:
            raise PathLimitExceededError(
                "Rendered absolute path exceeds the configured path limit.",
                script_name=script_name,
                line=1,
                column=1,
            )
        if compatibility.windows_legacy_path_limit and len(absolute_text) > 259:
            raise PathLimitExceededError(
                "Rendered path exceeds the enabled Windows 259-character limit.",
                script_name=script_name,
                line=1,
                column=1,
            )
        collision_key = "/".join(
            unicodedata.normalize("NFC", part).casefold() for part in cleaned
        )
        return NamingRenderResult(
            relative_path=relative,
            collision_key=collision_key,
            rendered_characters=len(relative),
        )

    def format_management_literal_path(
        self,
        relative_path: str,
        compatibility: PathCompatibilitySettings,
        *,
        script_name: str = "naming script",
        root: Path | None = None,
    ) -> NamingRenderResult:
        """Normalize an already-literal relative path without template parsing.

        F-075: composed fallback paths (e.g. ``<album-dir>/cover.jpg``) must
        never be re-parsed as template source - brace-bearing directory names
        are legal filename characters, and treating them as template bodies
        silently redirects writes or fails with a misleading script error.
        Applies exactly the output-side pipeline of ``format_management_path``:
        per-component cleaning, length limits, and collision-key construction.
        """

        raw_path = relative_path
        parts = raw_path.split("/")
        if (
            not raw_path
            or raw_path.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ScriptValidationError(
                "Naming script rendered an empty, absolute, or traversing path.",
                script_name=script_name,
                line=1,
                column=1,
            )
        cleaned = tuple(
            self._clean_management_component(
                part,
                compatibility,
                preserve_suffix=(index == len(parts) - 1),
            )
            for index, part in enumerate(parts)
        )
        relative = "/".join(cleaned)
        encoded_length = len(relative.encode("utf-8"))
        if encoded_length > compatibility.maximum_path_length:
            raise PathLimitExceededError(
                "Rendered relative path exceeds the configured path limit.",
                script_name=script_name,
                line=1,
                column=1,
            )
        absolute_text = str(root / Path(relative)) if root is not None else relative
        if len(absolute_text.encode("utf-8")) > compatibility.maximum_path_length:
            raise PathLimitExceededError(
                "Rendered absolute path exceeds the configured path limit.",
                script_name=script_name,
                line=1,
                column=1,
            )
        if compatibility.windows_legacy_path_limit and len(absolute_text) > 259:
            raise PathLimitExceededError(
                "Rendered path exceeds the enabled Windows 259-character limit.",
                script_name=script_name,
                line=1,
                column=1,
            )
        collision_key = "/".join(
            unicodedata.normalize("NFC", part).casefold() for part in cleaned
        )
        return NamingRenderResult(
            relative_path=relative,
            collision_key=collision_key,
            rendered_characters=len(relative),
        )

    @staticmethod
    def _legacy_segments(template: str) -> list[tuple[str, bool]]:
        """Split a legacy template into literal and variable segments.

        A nested ``{variable}`` inside an outer brace pair is kept as the
        variable segment, which makes a template-authored ``{}`` decoration
        distinguishable from the variable's own braces.  Braces that do not
        contain a non-empty variable remain literal text, as they did with
        ``_TOKEN``.
        """
        segments: list[tuple[str, bool]] = []
        literal_start = 0
        index = 0
        length = len(template)
        while index < length:
            if template[index] != "{":
                index += 1
                continue
            end = index + 1
            while end < length and template[end] not in "{}":
                end += 1
            if end >= length:
                break
            if template[end] == "{":
                index = end
                continue
            if end == index + 1:
                index = end + 1
                continue
            segments.append((template[literal_start:index], False))
            segments.append((template[index : end + 1], True))
            index = end + 1
            literal_start = index
        segments.append((template[literal_start:], False))
        return segments

    @staticmethod
    def _empty_group_boundaries(
        segments: list[tuple[str, bool]], token_index: int
    ) -> tuple[int, int] | None:
        """Return offsets for a matching empty, non-nested decoration."""
        if token_index == 0 or token_index + 1 >= len(segments):
            return None
        before, before_is_token = segments[token_index - 1]
        after, after_is_token = segments[token_index + 1]
        if before_is_token or after_is_token:
            return None

        opening_index = len(before) - 1
        while opening_index >= 0 and before[opening_index].isspace():
            opening_index -= 1
        if opening_index < 0:
            return None
        outer_opening_index = opening_index - 1
        while outer_opening_index >= 0 and before[outer_opening_index].isspace():
            outer_opening_index -= 1
        if outer_opening_index >= 0 and before[outer_opening_index] in "([{":
            return None
        opening = before[opening_index]
        closing = {"(": ")", "[": "]", "{": "}"}.get(opening)
        if closing is None:
            return None

        closing_index = 0
        while closing_index < len(after) and after[closing_index].isspace():
            closing_index += 1
        if closing_index >= len(after) or after[closing_index] != closing:
            return None

        outer_closing_index = closing_index + 1
        while outer_closing_index < len(after) and after[outer_closing_index].isspace():
            outer_closing_index += 1
        if outer_closing_index < len(after) and after[outer_closing_index] in ")]}":
            return None

        before_start = opening_index
        while before_start > 0 and before[before_start - 1].isspace():
            before_start -= 1
        return before_start, closing_index + 1

    def _render(self, template: str, tag: AudioTag, ext: str) -> Path:
        segments = self._legacy_segments(template)
        rendered_values: dict[int, str] = {}
        dropped_tokens: set[int] = set()
        literal_prefix_ends: dict[int, int] = {}
        literal_suffix_starts: dict[int, int] = {}

        for index, (part, is_token) in enumerate(segments):
            if not is_token:
                continue
            var, _, fmt = part[1:-1].partition(":")
            value = self._lookup(var, tag, ext)
            if fmt and var in self._FORMATTED:
                try:
                    value = format(int(value), fmt)
                except (ValueError, TypeError):
                    value = "00"
            rendered_values[index] = value
            if value:
                continue
            boundaries = self._empty_group_boundaries(segments, index)
            if boundaries is None:
                continue
            before_start, after_end = boundaries
            dropped_tokens.add(index)
            before_index = index - 1
            after_index = index + 1
            literal_suffix_starts[before_index] = min(
                literal_suffix_starts.get(before_index, len(segments[before_index][0])),
                before_start,
            )
            literal_prefix_ends[after_index] = max(
                literal_prefix_ends.get(after_index, 0),
                after_end,
            )

        result: list[str] = []
        for index, (part, is_token) in enumerate(segments):
            if is_token:
                if index in dropped_tokens:
                    continue
                # Sanitise substituted values so a value containing "/" (or
                # other invalid chars) can't inject path components - only
                # the template's literal separators define structure.
                result.append(self._INVALID_FS_CHARS.sub("_", rendered_values[index]))
                continue
            start = literal_prefix_ends.get(index, 0)
            end = literal_suffix_starts.get(index, len(part))
            if start < end:
                result.append(part[start:end])
        # Literals already carry the "/" separators; Path() splits them into
        # components, which _normalize then cleans individually.
        return Path("".join(result))

    def _lookup(self, var: str, tag: AudioTag, ext: str) -> str:
        match var:
            case "artist":
                return tag.artist
            case "album":
                return tag.album
            case "albumartist":
                return tag.album_artist or tag.artist
            case "initial":
                return _artist_initial(tag.album_artist or tag.artist, "NFC")
            case "year":
                return str(tag.year) if tag.year else ""
            case "title":
                return tag.title
            case "ext":
                return ext
            case "track":
                return str(tag.track_number)
            case "disc":
                return str(tag.disc_number)
            case "genre":
                return tag.genre or ""
            case "medium":
                return ""  # populated by the caller if known (MB lookup, not template)
            case "musicbrainz_id":
                return tag.musicbrainz_release_group_id or ""
            case "artist_mbid":
                return tag.musicbrainz_artist_id or ""
            case _:
                return ""  # unknown variable renders empty (lenient; validate_template is strict)

    def _normalize(self, path: Path) -> Path:
        parts: list[str] = []
        for component in path.parts:
            # Drop the filesystem root so an absolute render (e.g. an empty
            # leading variable) can never escape library_root - output is always
            # relative.
            if path.anchor and component == path.anchor:
                continue
            parts.append(self._clean_component(component))
        return Path("/".join(parts)) if parts else Path("_")

    @staticmethod
    def _script_text(value: ScriptValue) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, tuple):
            return "; ".join(value)
        return str(value)

    @classmethod
    def _sanitize_substituted_value(
        cls,
        value: str,
        replacement: str,
        windows_compatible: bool,
    ) -> str:
        pattern = (
            cls._INVALID_FS_CHARS
            if windows_compatible
            else cls._ALWAYS_INVALID_VALUE_CHARS
        )
        return pattern.sub(replacement, value)

    @classmethod
    def _clean_management_component(
        cls,
        component: str,
        compatibility: PathCompatibilitySettings,
        *,
        preserve_suffix: bool = False,
    ) -> str:
        replacement = compatibility.separator_replacement
        cleaned = unicodedata.normalize(compatibility.unicode_normalization, component)
        pattern = (
            cls._INVALID_FS_CHARS
            if compatibility.windows_compatible
            else cls._ALWAYS_INVALID_VALUE_CHARS
        )
        cleaned = pattern.sub(replacement, cleaned)
        if compatibility.replace_non_ascii:
            folded = (
                unicodedata.normalize("NFKD", cleaned)
                .encode("ascii", "ignore")
                .decode()
            )
            cleaned = folded or replacement
        if compatibility.replace_spaces_with_underscores:
            cleaned = cleaned.replace(" ", "_")
        if compatibility.windows_compatible:
            cleaned = cleaned.strip(" .")
            if cleaned and cleaned.split(".", 1)[0].casefold() in _RESERVED_NAMES:
                cleaned = f"{replacement}{cleaned}"
        if not cleaned:
            cleaned = replacement
        encoded = cleaned.encode("utf-8")
        maximum = compatibility.maximum_component_length
        if len(encoded) > maximum:
            if preserve_suffix:
                suffix = Path(cleaned).suffix
                suffix_bytes = suffix.encode("utf-8")
                if (
                    suffix
                    and len(suffix_bytes) < maximum
                    and cleaned.endswith(suffix)
                ):
                    stem = cleaned[: -len(suffix)]
                    budget = maximum - len(suffix_bytes)
                    truncated_stem = (
                        stem.encode("utf-8")[:budget].decode("utf-8", "ignore")
                    )
                    if compatibility.windows_compatible:
                        truncated_stem = truncated_stem.rstrip(" .")
                    candidate = f"{truncated_stem}{suffix}"
                    if not candidate:
                        candidate = replacement
                    cleaned = candidate
                else:
                    cleaned = encoded[:maximum].decode("utf-8", "ignore")
                    cleaned = (
                        cleaned.strip(" .")
                        if compatibility.windows_compatible
                        else cleaned
                    )
                    if not cleaned:
                        cleaned = replacement
            else:
                cleaned = encoded[:maximum].decode("utf-8", "ignore")
                cleaned = (
                    cleaned.strip(" .") if compatibility.windows_compatible else cleaned
                )
                if not cleaned:
                    cleaned = replacement
            if (
                compatibility.windows_compatible
                and cleaned.split(".", 1)[0].casefold() in _RESERVED_NAMES
            ):
                cleaned = f"{replacement}{cleaned}"
                cleaned = cleaned.encode("utf-8")[:maximum].decode("utf-8", "ignore")
        return cleaned

    @classmethod
    def _management_variables(
        cls,
        document: ReadAudioDocument,
        compatibility: PathCompatibilitySettings,
        *,
        artwork_type: str,
        artwork_comment: str,
        artwork_extension: str,
        artwork_format: str,
        naming_context: ManagementNamingContext | None,
    ) -> dict[str, ScriptValue]:
        metadata = document.metadata
        variables: dict[str, ScriptValue] = {
            field.name: field.value for field in metadata.fields
        }
        artists = metadata.strings_for("artist")
        album_artists = metadata.strings_for("album_artist")
        artist_sorts = metadata.strings_for("artist_sort")
        album_artist_sorts = metadata.strings_for("album_artist_sort")
        genres = metadata.strings_for("genre")
        date = metadata.value_for("date")
        extension = document.probe.extension.removeprefix(".")
        if compatibility.extension_case == "lower":
            extension = extension.lower()
        elif compatibility.extension_case == "upper":
            extension = extension.upper()
        bitrate = max(0, round(document.technical.bitrate_bps / 1000))
        albumartist = (
            metadata.album_artist_display
            or (album_artists[0] if album_artists else "")
            or metadata.artist_display
            or (artists[0] if artists else "")
        )
        variables.update(
            artist=metadata.artist_display or (artists[0] if artists else ""),
            artists=artists,
            artist_display=metadata.artist_display or "",
            artist_sorts=artist_sorts,
            artist_sort=artist_sorts[0] if artist_sorts else "",
            album_artist=(
                metadata.album_artist_display
                or (album_artists[0] if album_artists else "")
            ),
            albumartist=albumartist,
            initial=_artist_initial(
                albumartist,
                compatibility.unicode_normalization,
            ),
            album_artists=album_artists,
            album_artist_display=metadata.album_artist_display or "",
            album_artist_sorts=album_artist_sorts,
            album_artist_sort=(album_artist_sorts[0] if album_artist_sorts else ""),
            genre=genres[0] if genres else "",
            genres=genres,
            primary_genre=genres[0] if genres else "",
            year=(date[:4] if isinstance(date, str) else ""),
            track=metadata.value_for("track_number"),
            disc=metadata.value_for("disc_number"),
            ext=extension,
            extension=extension,
            medium=metadata.value_for("media"),
            musicbrainz_id=metadata.value_for("musicbrainz_release_group_id"),
            artist_mbid=(metadata.strings_for("musicbrainz_artist_id") or ("",))[0],
            codec=document.technical.codec or document.probe.detected_format,
            quality=(
                "lossless"
                if document.technical.bit_depth is not None
                else f"{bitrate}kbps"
            ),
            bitrate=bitrate,
            sample_rate=document.technical.sample_rate_hz,
            bit_depth=document.technical.bit_depth,
            artwork_type=artwork_type,
            artwork_comment=artwork_comment,
            artwork_extension=artwork_extension,
            artwork_format=artwork_format,
            album_disambiguation=(
                naming_context.album_disambiguation if naming_context else ""
            ),
            medium_format=(naming_context.medium_format if naming_context else ""),
            medium_number=(naming_context.medium_number if naming_context else 0),
        )
        return variables

    @classmethod
    def _clean_component(cls, component: str) -> str:
        """Normalise one path component to a safe, contained filename."""
        cleaned = cls._INVALID_FS_CHARS.sub(
            "_", unicodedata.normalize("NFC", component)
        )
        # Strip leading/trailing dots+spaces (Windows-illegal; '.'/'..' would
        # otherwise act as path operators and traverse on join).
        cleaned = cleaned.strip(" .")
        if not cleaned:
            cleaned = "_"
        # Disarm reserved Windows device names (with or without extension).
        if cleaned.split(".", 1)[0].lower() in _RESERVED_NAMES:
            cleaned = f"_{cleaned}"
        encoded = cleaned.encode("utf-8")
        if len(encoded) > _MAX_COMPONENT_BYTES:
            cleaned = encoded[:_MAX_COMPONENT_BYTES].decode("utf-8", errors="ignore")
            cleaned = cleaned.strip(" .") or "_"
        return cleaned
