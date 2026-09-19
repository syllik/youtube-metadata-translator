#!/usr/bin/env python3
"""Safely preview and publish YouTube channel name/description localizations."""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("channel-localizations")
REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = REPO_ROOT / "data" / "channel-localizations.json"
_LANGUAGE_CODE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


class ChannelLocalizationError(RuntimeError):
    """Raised when channel localization input or verification is unsafe."""


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ChannelLocalizationError(
            f"Data file not found: {path}. Create the local ignored file first; "
            "see docs/channel-localizations.md."
        ) from error
    except json.JSONDecodeError as error:
        raise ChannelLocalizationError(f"Invalid JSON in {path}: {error}") from error

    if not isinstance(payload, dict):
        raise ChannelLocalizationError("Localization data must be a JSON object")

    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ChannelLocalizationError("Localization data must contain a non-empty entries list")

    expected_count = payload.get("expectedStudioLocaleCount")
    if expected_count is not None and expected_count != len(entries):
        raise ChannelLocalizationError(
            f"Expected {expected_count} Studio locales, found {len(entries)}"
        )

    seen_studio_locales: set[str] = set()
    required_fields = (
        "studioLocale",
        "studioName",
        "apiLanguage",
        "title",
        "description",
    )

    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ChannelLocalizationError(f"Entry {index} must be an object")
        missing = [
            field
            for field in required_fields
            if not isinstance(entry.get(field), str) or not entry[field].strip()
        ]
        if missing:
            raise ChannelLocalizationError(
                f"Entry {index} has missing/empty fields: {', '.join(missing)}"
            )

        studio_locale = entry["studioLocale"]
        api_language = entry["apiLanguage"]
        if studio_locale in seen_studio_locales:
            raise ChannelLocalizationError(f"Duplicate Studio locale: {studio_locale}")
        if "_" in api_language or not _LANGUAGE_CODE_RE.fullmatch(api_language):
            raise ChannelLocalizationError(
                f"Invalid API localization language code: {api_language}"
            )
        seen_studio_locales.add(studio_locale)

    return payload


def desired_localizations(
    payload: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Build the channel-localization map using exact YouTube Studio locale IDs.

    Live channel responses use Studio locale identifiers such as `en_US`,
    `af_ZA`, and `sr_Latn_RS` as `localizations` keys. Keep those exact
    identifiers for reads, diffs, and writes instead of normalizing them to
    BCP-47-style metadata-language codes.
    """
    return {
        entry["studioLocale"]: {
            "title": entry["title"],
            "description": entry["description"],
        }
        for entry in payload["entries"]
    }


def diff_localizations(
    existing: dict[str, dict[str, str]],
    desired: dict[str, dict[str, str]],
) -> list[tuple[str, str]]:
    changes: list[tuple[str, str]] = []
    for language, value in desired.items():
        current = existing.get(language)
        if current is None:
            status = "ADD"
        elif current == value:
            status = "UNCHANGED"
        else:
            status = "UPDATE"
        changes.append((language, status))
    return changes


def merged_localizations(
    existing: dict[str, dict[str, str]],
    desired: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    merged = dict(existing)
    merged.update(desired)
    return merged


def locale_key_overlap(
    existing: dict[str, dict[str, str]],
    desired: dict[str, dict[str, str]],
) -> list[str]:
    return sorted(set(existing) & set(desired))


def ensure_safe_overlap(
    existing: dict[str, dict[str, str]],
    desired: dict[str, dict[str, str]],
    *,
    applying: bool,
) -> list[str]:
    overlap = locale_key_overlap(existing, desired)
    if existing and not overlap and applying:
        raise ChannelLocalizationError(
            "Existing channel localizations have zero key overlap with the reviewed "
            "dataset. Do not publish until the actual YouTube API locale keys are "
            "mapped from a dry-run output."
        )
    return overlap


def fetch_channel_resource(youtube: Any, channel_id: str) -> dict[str, Any]:
    response = youtube.channels().list(
        part="snippet,brandingSettings,localizations",
        id=channel_id,
    ).execute()
    items = response.get("items") or []
    if len(items) != 1:
        raise ChannelLocalizationError(
            f"Expected one channel resource for {channel_id}, got {len(items)}"
        )
    return items[0]


def write_backup(channel: dict[str, Any], backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"channel-localizations-backup-{timestamp}.json"
    snapshot = {
        "channelId": channel.get("id"),
        "etag": channel.get("etag"),
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "defaultLanguage": (
            ((channel.get("brandingSettings") or {}).get("channel") or {}).get(
                "defaultLanguage"
            )
        ),
        "localizations": channel.get("localizations") or {},
    }
    backup_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return backup_path


def verify_desired(
    actual: dict[str, dict[str, str]],
    desired: dict[str, dict[str, str]],
) -> list[str]:
    return [
        language
        for language, value in desired.items()
        if actual.get(language) != value
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or publish channel title/description localizations using the "
            "existing local YouTube OAuth session. Dry-run is the default."
        )
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help=f"Localization JSON path (default: {DEFAULT_DATA_PATH})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Publish the merged localization map to YouTube.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=REPO_ROOT,
        help="Directory for the pre-write JSON backup (default: repository root).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)

    payload = load_catalog(args.data)
    desired = desired_localizations(payload)
    LOGGER.info(
        "Loaded %d reviewed Studio locale keys from %s",
        len(desired),
        args.data,
    )

    # Import lazily so credential-free unit tests do not require Google client libs.
    from youtube_account import YoutubeApi

    api = YoutubeApi()
    if api.errorStr:
        raise ChannelLocalizationError(
            f"YouTube API initialization failed: {api.errorStr}"
        )
    if not api.channel_id:
        raise ChannelLocalizationError("Authenticated YouTube channel ID is missing")

    channel = fetch_channel_resource(api.youtube, api.channel_id)
    branding_channel = (
        (channel.get("brandingSettings") or {}).get("channel") or {}
    )
    default_language = branding_channel.get("defaultLanguage")
    if not default_language:
        raise ChannelLocalizationError(
            "Channel defaultLanguage is not set. Set the original channel language "
            "in YouTube Studio before publishing localizations."
        )

    existing = channel.get("localizations") or {}
    if not isinstance(existing, dict):
        raise ChannelLocalizationError(
            "YouTube returned an invalid localizations object"
        )

    LOGGER.info(
        "Channel %s | default language: %s | existing localizations: %d",
        api.channel_id,
        default_language,
        len(existing),
    )
    if existing:
        LOGGER.info("Existing localization keys: %s", ", ".join(sorted(existing)))

    overlap = ensure_safe_overlap(existing, desired, applying=args.apply)
    LOGGER.info(
        "Locale-key overlap: %d existing keys match the reviewed dataset",
        len(overlap),
    )
    if existing and not overlap:
        warning = (
            "Existing channel localizations have zero key overlap with the reviewed "
            "dataset. Do not publish until the actual YouTube API locale keys are "
            "mapped from this dry-run output."
        )
        LOGGER.warning(warning)

    changes = diff_localizations(existing, desired)
    for language, status in changes:
        LOGGER.info("%-9s %s", status, language)

    changed_count = sum(
        1 for _language, status in changes if status != "UNCHANGED"
    )
    LOGGER.info(
        "Summary: %d desired | %d changed | %d unchanged",
        len(desired),
        changed_count,
        len(desired) - changed_count,
    )

    if not args.apply:
        LOGGER.info(
            "DRY RUN: no YouTube write performed. Re-run with --apply to publish."
        )
        return 0

    if changed_count == 0:
        LOGGER.info("No changes to publish.")
        return 0

    backup_path = write_backup(channel, args.backup_dir)
    LOGGER.info("Backup written: %s", backup_path)

    merged = merged_localizations(existing, desired)
    request = api.youtube.channels().update(
        part="localizations",
        body={"id": api.channel_id, "localizations": merged},
    )
    etag = channel.get("etag")
    if etag:
        request.headers["If-Match"] = etag
    request.execute()
    LOGGER.info(
        "Published %d desired localizations; preserved %d existing keys total",
        len(desired),
        len(existing),
    )

    fresh = fetch_channel_resource(api.youtube, api.channel_id)
    actual = fresh.get("localizations") or {}
    mismatches = verify_desired(actual, desired)
    if mismatches:
        raise ChannelLocalizationError(
            "Post-write verification failed for: " + ", ".join(mismatches)
        )

    LOGGER.info(
        "VERIFY OK: %d/%d desired localizations match YouTube",
        len(desired),
        len(desired),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ChannelLocalizationError as error:
        LOGGER.error("%s", error)
        raise SystemExit(1) from error
