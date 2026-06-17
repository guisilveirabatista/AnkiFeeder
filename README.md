# AnkiFeeder

Watch an Obsidian note and automatically turn each word in it into an Anki
flashcard, complete with its translation (or definition) and example sentences.

- **Input:** a markdown note in your Obsidian vault, one word (or phrase) per line,
  written in your configured `source_language`.
- **Output:** a "Basic" card in your chosen Anki deck — **Front** = the word,
  **Back** = its `target_language` translation plus an example sentence in each
  language. Set `source_language` and `target_language` to the **same** language
  to get a definition instead of a translation (a monolingual dictionary card).
- Runs continuously and adds new words the moment you save the note.
- Translation and examples come from a translation backend of your choice —
  **Claude**, **OpenAI**, **Gemini**, or a **local model** (Ollama, LM Studio, …).

## How it connects to Anki

There's no public API for AnkiWeb directly, so AnkiFeeder talks to your
**desktop Anki** through the **AnkiConnect** add-on. Cards you add then sync up
to your AnkiWeb account like any other change.

### One-time setup

1. **Install AnkiConnect** in the Anki desktop app:
   *Tools → Add-ons → Get Add-ons…* and paste code **`2055492159`**, then
   restart Anki.
2. Leave Anki **running** whenever you want words to sync.

## Setup

Requires Python 3.10+ (you have 3.13). From this folder:

```bash
python3 -m venv .venv && source .venv/bin/activate   # recommended
pip install -r requirements.txt                      # installs the anthropic SDK
export ANTHROPIC_API_KEY=sk-ant-...                  # your Claude API key
python3 -m ankifeeder init                           # writes config.json from a template
```

Open `config.json` and set `note_path` to your Obsidian note. Options:

| Key                | Meaning                                                        |
| ------------------ | -------------------------------------------------------------- |
| `note_path`        | Path to the note to read (supports `~`). **Required.**         |
| `deck_name`        | Anki deck to add to (created automatically if missing).        |
| `anki_connect_url` | AnkiConnect endpoint. Default `http://127.0.0.1:8765`.         |
| `model_name`       | Anki note type. `Basic` (Front/Back) is expected.              |
| `source_language`  | Language the note's words are written in. Default `English`.   |
| `target_language`  | Language to translate into. Default `Dutch`. Set it equal to `source_language` for definition cards instead of translations. |
| `claude_model`     | Claude model for translation. Default `claude-opus-4-8`.       |
| `poll_interval`    | Seconds between checks of the note file while watching.        |
| `settle_delay`     | After a save is noticed, wait until the note has been quiet this many seconds before syncing, so a sentence you're still writing (or a fast Obsidian sync mid-write) isn't picked up half-finished. Default `10`; `0` syncs as soon as a change lands. |
| `retry_interval`   | Seconds between forced full re-scans while watching, so words that failed all attempts get retried without re-saving the note. Default `1800` (30 min); `0` disables. |
| `request_delay`    | Seconds to wait between successive translations (throttling).  |
| `max_retries`      | Extra attempts on a transient (rate-limit/overload) error.    |
| `retry_backoff`    | Base seconds for exponential backoff between those attempts.   |
| `tag`              | Tag applied to every card AnkiFeeder creates.                  |

The API key is read from an environment variable — it is never stored in
`config.json`.

### Translation backends

Choose a backend with `translator` and set the matching model + credentials.
Imports are lazy, so you only need the SDK/server for the backend you use.

| `translator` | Model key      | Credential                            |
| ------------ | -------------- | ------------------------------------- |
| `claude`     | `claude_model` | `ANTHROPIC_API_KEY` env var           |
| `openai`     | `openai_model` | `OPENAI_API_KEY` env var              |
| `gemini`     | `gemini_model` | `GEMINI_API_KEY` env var              |
| `local`      | `local_model`  | `local_base_url` (+ optional `local_api_key`) |

For a **local model** via Ollama, run `ollama pull <model>` and point
`local_base_url` at its OpenAI-compatible endpoint (default
`http://localhost:11434/v1`). Nothing leaves your machine. All backends share the
same structured-output schema, so the cards come out identical.

## Usage

```bash
python3 -m ankifeeder watch   # watch the note and add words as you save (default)
python3 -m ankifeeder sync    # add any new words once, then exit
```

Point at a specific config file with `-c` (defaults to `config.json`):

```bash
python3 -m ankifeeder -c dutch.json watch
```

### Run from anywhere

A wrapper script in `bin/` runs AnkiFeeder with the project's virtualenv and
`config.json` from any directory. Add it to your `PATH` once:

```bash
echo 'export PATH="$PATH:'"$PWD"'/bin"' >> ~/.zshrc
source ~/.zshrc
```

Then just use `ankifeeder` (it still accepts `-c` for an alternate config):

```bash
ankifeeder watch
ankifeeder sync
ankifeeder -c dutch.json watch
```

## Multiple notes → multiple decks

To feed several notes into several decks, add a `feeds` list to one config. Each
feed inherits the shared top-level settings (translator, delays, AnkiConnect URL,
…) and overrides per-note fields like `note_path`, `deck_name`, and the
`source_language` / `target_language` pair. A single `watch` then runs every feed
concurrently in one process:

```json
{
  "translator": "gemini",
  "gemini_model": "gemini-2.5-flash-lite",
  "request_delay": 2.0,
  "source_language": "English",
  "target_language": "Dutch",
  "feeds": [
    { "note_path": "~/Obsidian/dutch/vocab.md",    "deck_name": "Dutch::Vocabulary" },
    { "note_path": "~/Obsidian/french/vocab.md",   "deck_name": "French::Vocabulary", "target_language": "French" },
    { "note_path": "~/Obsidian/english/words.md",  "deck_name": "English::Definitions", "target_language": "English" }
  ]
}
```

Here the shared default is English→Dutch; the second feed overrides the target to
French, and the third sets target = source ("English") so it produces definition
cards.

```bash
python3 -m ankifeeder -c multi.json watch   # watches all three at once
```

Each feed gets its **own** dedup state file (derived from the note name unless
you set `state_path`), so feeds never interfere. See
`config.multi.example.json`. The two strategies compose: run one multi-feed
process, or several single-feed processes each with their own `-c` file —
whichever you prefer.

## How the note is read

Each non-empty line becomes one card. The parser ignores headings (`#`),
block quotes (`>`), and horizontal rules, and strips list markers and links, so
this note:

```markdown
# My vocab
- ephemeral
- [[serendipity]]
- gregarious
```

produces three cards: `ephemeral`, `serendipity`, `gregarious`.

## Notes & behavior

- **No duplicates.** Added words are recorded in `.ankifeeder_state.json`, and
  AnkiConnect also rejects duplicates within the deck — so re-running is safe.
- **Translation failed?** The word is *not* recorded, so the next run retries it
  (transient API errors won't leave gaps). Each word is also retried up to
  `max_retries` times in place, with exponential backoff (see `retry_backoff`).
- **Still typing?** While watching, the line you're currently on — the last line,
  before you've pressed Enter — is treated as in progress and is *not* imported, so
  a half-written entry like "This is a t" never becomes a card. Pressing Enter (or
  starting the next entry) commits the line and it's imported on the next scan. As
  an extra cushion, after any save the watcher also waits until the note has been
  quiet for `settle_delay` seconds (default 10) before syncing, which smooths over
  edits to earlier lines and fast Obsidian syncs landing mid-write.
- **Stuck after all retries?** While watching, the note is re-scanned every
  `retry_interval` seconds (default 30 min) even if you haven't saved it, so words
  that exhausted their attempts get picked up automatically — no restart needed.
- **Anki not running / no API key?** You'll get a clear message; while watching,
  errors are logged and the watcher keeps going so it recovers once fixed.