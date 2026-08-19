# Swahili Read-Aloud Audit Report

## Scope

- Audited 7,501 text entries in each of `sw` and `sw-TZ`.
- Audited 7,451 mapped read-aloud IDs, including 2,786 `_easy_read` IDs.
- Inspected 208 page/quiz HTML files and 3,380 unique HTML `data-id` values.
- Audited 321 image instances.
- Regenerated mapped audio with `sw-TZ-DaudiNeural` at `-5%`.
- Used `en-TZ-ElimuNeural` for identified English/acronym/URL segments.
- Copied each generated result to the matching `sw` and `sw-TZ` destinations.

## Spoken-text rules

- Expanded `Dkt.`, `Bw.`, `Bi.`, `Prof.`, and `Na.` only in spoken text.
- Spelled identified acronyms and ISBN content with an English voice.
- Converted Roman numerals I-VI to Swahili numbers.
- Converted numbered `Zoezi`, `Jaribio`, and `Kazi ya kufanya` headings to ordinals.
- Converted numbered `Kielelezo` labels to `Kielelezo cha ...` ordinals.
- Read isolated list letters as `a`, `be`, `che`, and `de`.
- Changed `a mpaka d` to spoken `a mpaka de`.
- Removed `[[blank:...]]` tokens; token-only answer fields now use nonempty silent MP3s.
- Preserved subtraction as `toa`; compact digit ranges use `hadi`.
- Removed repeated bracketed digits after Swahili number words.
- Expanded arrows to `inaelekea` and `inatoka`.
- Added terminal pauses to short isolated labels and table cells.
- Split identified mixed Swahili/English passages into voice-specific segments.
- Spelled URLs using `colon`, `slash`, `dot`, and `hyphen`, with domain initials articulated separately.

## Image descriptions

- Verified every image has a nonempty Swahili description, an audio mapping, and an existing audio file in both locales.
- Consolidated 46 repeated same-ID image instances at runtime: the first is described and focusable; later identical instances are decorative. Distinct images retain separate descriptions.

## Files changed

- `scripts/regenerate_tanzanian_audio.py`
- `scripts/audit_read_aloud.py`
- `assets/enable-image-descriptions.js`
- `assets/offline-preloader.js`
- `content/i18n/sw/audios.json`
- `content/i18n/sw-TZ/audios.json`
- All mapped MP3 destinations under `content/i18n/sw/audio/` and `content/i18n/sw-TZ/audio/`
- This report and the detailed files under `tmp/read-aloud/`

No visible textbook wording, text IDs, filenames, HTML reading order, compiled runtime modules, or compiled Tailwind CSS were changed for this audit.

## Automated checks

- All JSON parsed successfully.
- Every mapped MP3 exists and is nonempty.
- `sw` and `sw-TZ` text catalogs and audio maps match.
- Every mapped `sw` MP3 is byte-identical to its `sw-TZ` counterpart.
- Every `_easy_read` mapping has a normal mapping.
- Every described image has matching HTML alt text, catalog text, audio mapping, and audio file.
- Printed-text sentinels confirmed that phonetic replacements did not enter visible text.
- Final audit result: zero errors.

## Detailed results

- `tmp/read-aloud/affected_text_ids.txt`: every regenerated/mapped text ID.
- `tmp/read-aloud/all-spoken-manifest.json`: visible text, spoken segments, and selected voices for every ID.
- `tmp/read-aloud/rule-affected-ids.json`: IDs grouped by pronunciation rule.
- `tmp/read-aloud/human_listening_review.json`: short isolated words, mixed names, URLs, and other entries recommended for human listening review, with their planned spoken segments.
- `tmp/read-aloud/image_group_instances.json`: repeated same-ID image groups consolidated at runtime.
- `tmp/read-aloud/audit-summary.json`: machine-readable final results.

## Human listening review

Automated checks cannot judge voice naturalness. The review list contains 968 conservative candidates, primarily isolated one- or two-word labels, personal names/initials, technical terms, and mixed-language/Internet content. These do not represent known failures; they are the entries where a native-speaker listening pass has the highest value.
