# 🌐 Channel profile localizations

Use `update_channel_localizations.py` when you want to translate the **YouTube
channel name and channel description**. This is separate from the Streamlit
video-title and video-description workflow.

## Local data file

Create this file locally:

```text
data/channel-localizations.json
```

It is intentionally ignored by Git because the translations are channel-specific
user data. Do not force-add or commit it.

The script expects a JSON object with an `entries` array. Each entry contains
the exact YouTube Studio locale ID plus the translated channel title and
description:

```json
{
  "schemaVersion": 1,
  "entries": [
    {
      "studioLocale": "en_US",
      "studioName": "English",
      "apiLanguage": "en",
      "title": "Localized channel name",
      "description": "Localized channel description"
    },
    {
      "studioLocale": "fr_FR",
      "studioName": "French",
      "apiLanguage": "fr",
      "title": "Nom de chaîne localisé",
      "description": "Description de chaîne localisée"
    }
  ]
}
```

`studioLocale` is the key used for channel-localization reads and writes. Keep
the exact Studio form such as `en_US`, `fr_FR`, or `sr_Latn_RS`. The
`apiLanguage` field is informational and is not used as the write key.

An optional `expectedStudioLocaleCount` field can be added when you want the
script to fail if the number of entries changes unexpectedly.

## Preview first

Activate the same virtual environment and OAuth setup used by the app, then run:

```bash
python update_channel_localizations.py
```

This is read-only. It prints the authenticated channel, the channel default
language, existing localization keys, locale-key overlap, and one status for
each desired locale:

- `ADD` — the locale does not exist yet.
- `UPDATE` — the locale exists but its title or description differs.
- `UNCHANGED` — the stored value already matches.

If the channel already has localizations but none of their keys overlap the
local file, do not publish. The script blocks `--apply` in this situation so
you can correct the locale mapping first.

## Publish

After reviewing the dry-run output:

```bash
python update_channel_localizations.py --apply
```

Before writing, the script saves a timestamped local JSON backup of the current
channel-localization state. It then merges the desired entries with unrelated
existing localizations, sends the channel localization update, and performs a
fresh read to verify every desired value.

The channel must already have a default language configured in YouTube Studio.

## Custom data path

You can keep the local translation file elsewhere:

```bash
python update_channel_localizations.py --data /path/to/channel-localizations.json
python update_channel_localizations.py --data /path/to/channel-localizations.json --apply
```

Keep OAuth files, tokens, backups, and channel-specific translation data out of
version control.
