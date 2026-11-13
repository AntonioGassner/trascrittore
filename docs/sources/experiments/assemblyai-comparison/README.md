# Running the AssemblyAI trial

The code that runs the trial described in [spec.md](spec.md), and, once the trial
is over, its `report.md`. It is experiment material: nothing here is part of the
transcriber that people install, and the image never receives this folder.

## What is where

| Path | Content |
|---|---|
| `spec.md` | the method, the measures and the rule for the verdict, fixed before the first run |
| `trial.py` | the command that runs one step |
| `assemblyai_trial/trial_set.py` | the trial set and the maintainer's approval |
| `assemblyai_trial/assemblyai.py` | the four calls to AssemblyAI's European endpoint |
| `assemblyai_trial/transcript_form.py` | AssemblyAI's answer as a transcript of the transcriber's form |
| `assemblyai_trial/words.py`, `alignment.py`, `scorer.py` | normalization, word alignment and the scores against a curated transcript |
| `assemblyai_trial/blind.py`, `judging.py` | the blind comparison: the passages, the session, the key |
| `assemblyai_trial/verdict.py` | the rule for the verdict |
| `assemblyai_trial/report.py` | the report, made of figures only |
| `tests/` | the conversion, the scorer and the verdict rule, on invented input |

Everything else the trial produces stays in the trial's folder, which every
command takes as `--trial-dir` and refuses when it is inside the repository:

| In the trial's folder | Content |
|---|---|
| `trial-set.json` | the list of recordings; its form is at the top of `trial_set.py` |
| `key-terms/` | the key terms of the second run, one file per recording, one term per line |
| `sound/` | the mono sound files that are uploaded |
| `transcriber/<id>/` | the transcriber's transcripts of today |
| `assemblyai/plain/`, `assemblyai/terms/` | AssemblyAI's answers as they arrived, their state and their transcripts |
| `scores/<id>.json` | the scores of every transcript, with the per-passage tables |
| `blind/` | the passages, the stretches to hear, the answers and the key |
| `events.jsonl` | every attempt of every step, failed ones included |

## Before the first run

- `uv sync`, ffmpeg on `PATH`, and `ASSEMBLYAI_API_KEY=...` in the repository's
  `.env`, beside the Hugging Face token. No command prints the key.
- The checkout holds the transcriber as it is on `main`: this branch adds only
  this folder.
- The trial needs no dependency beyond the transcriber's own: the calls to
  AssemblyAI use Python's standard library.

## The steps

Each step is one command, here with `check`:

```powershell
.venv\Scripts\python docs\sources\experiments\assemblyai-comparison\trial.py --trial-dir D:\prova-assemblyai check
```

1. **Propose the trial set.** The agent writes `trial-set.json` with every
   eligible recording, `"approved": false` and `"approved_on": null`, and the
   key terms of each: the names of the folders in the voice library and the
   terms of the client's glossary, as they stand. `check` lists what is wrong,
   then the recordings with their length and the list price.
2. **Approval.** The agent shows the maintainer that list and
   [what AssemblyAI keeps](#what-assemblyai-keeps). The maintainer strikes what
   must not leave the PC. Only then the agent sets `"approved": true` on the
   others and `"approved_on"` to the day. Until then every other step refuses to
   run, and afterwards it refuses any recording that is not approved.
3. **One short recording first.** Run steps 4 to 6 with `--only <id>` and look
   at the transcripts and at `scores/<id>.json` before the whole set goes out.
   Steps 7 and 8 work on whatever is scored for both contenders, so they can be
   tried on that recording too: write the report elsewhere with `--out`, then
   delete `blind/` so that the passages are drawn again from the whole set.
4. **`transcribe`** runs the transcriber's own command line on each recording,
   with the settings of this checkout and without the number of speakers, into
   `transcriber/`. The recordings do not move and no existing transcript changes.
5. **`assemblyai`** extracts the sound, uploads it, saves the answer and deletes
   the transcript from AssemblyAI, which deletes the upload with it; a
   transcription that failed is deleted in the same way. `--run plain` is the
   run the verdict rests on; `--run terms` adds the key terms. A run that was
   interrupted fetches the transcript it was waiting for.
6. **`score`** converts the saved answers again and scores the stored
   transcript, the transcriber's and AssemblyAI's against the curated one.
7. **`blind-prepare`** draws the passages once. The maintainer runs
   **`blind-judge`** in a terminal of their own: each passage plays by itself
   and takes one key. `q` stops; the same command resumes.
8. **`report --charged <dollars>`** writes `report.md` here, with the verdict
   once every passage is answered. The charge is read from the Cost page of
   AssemblyAI's dashboard: its API does not state it. A recording that one
   contender never transcribed is left out of the figures and named, by its
   label only, under Reliability.

Every step skips the recordings it has finished. To repeat one, delete what it
wrote for that recording in the trial's folder.

## What AssemblyAI keeps

As its pages stated on 2026-11-13; the maintainer sees this before approving.

- **Where.** `api.eu.assemblyai.com` processes sound and transcripts in the
  European Union. Account and usage data are stored in the United States, and
  staff outside the region may access a sound file or a transcript for
  debugging.
  ([regions](https://www.assemblyai.com/docs/pre-recorded-audio/select-the-region))
- **How long.** Without other settings, deletion of an uploaded file starts
  after 24 hours and ends within 48; a transcript, and the key terms sent with
  it, are deleted after 30 days. Deleting a transcript through the API deletes
  the uploaded file with it at once, which is what the trial does. Some metadata
  stays for logging and billing. Pre-recorded transcription has no zero
  retention.
  ([retention](https://www.assemblyai.com/docs/data-retention-and-model-training))
- **Training.** The documentation and the security page say that files sent to
  the European servers are never used to train models. The Terms of Service
  (1 July 2026, section 4.3) grant a licence to train on customer data, with an
  opt-out that depends on the plan, and name no European exception; free
  accounts cannot opt out.
  ([security](https://www.assemblyai.com/security),
  [terms](https://www.assemblyai.com/legal/terms-of-service))
- **Key terms** hold names of people from the voice library. They go to
  AssemblyAI with the second run only.

## Choices the spec left to the code

- **Normalization.** Accents are dropped, apostrophes are one character, a
  hyphen joins its two halves, and a point or comma between two digits goes.
  Fillers are `eh`, `ehm`, `mh`, `mmh`, `hm`, `uh`, `uhm`, `ah`, `oh`, their
  longer spellings, and `cioè`. An immediate repetition is the same one to
  three words said twice in a row.
- **Marks.** `[non trascritto…]`, `[incomprensibile…]`, `[incerto: «…»]` and
  `[non registrato…]` are marks, the last reported apart. Any other square
  bracket is a note of the curation and counts as nothing. The words are
  aligned as if there were no marks; the extra words that fall exactly where a
  mark sits, between the two curated words around it, are the words written at
  it. So a word that fits a curated word is never given to a mark, and recovered
  speech is not overstated.
- **What is not speech.** After the first turn, a heading, a quote, a rule, a
  list item or a table row is skipped. A line that opens in bold without being
  a turn stops the scorer: `check` reports it.
- **Corrected words** are substitutions of words of three letters or more that
  are neither figures nor in the list of function words in `scorer.py`.
- **Speakers** are paired one to one, largest overlap first. Unattributed
  speech belongs to nobody; words whose speaker the curation left uncertain are
  not counted.
- **Possibly invented text** is a run of 8 or more words in a row that the
  curated transcript has not: extra words, or words written in place of others.
- **Passages.** 60 at differences, at least 15 of them from in-person
  recordings; up to 15 more at marks where a contender wrote words; up to 20
  more at possibly invented runs. No two passages overlap. Each is cut from the
  recording by the trial itself: the transcriber's passage player plays one
  segment, which is rarely 10 to 20 seconds long.
- **W and L** of the verdict count every passage of the blind comparison,
  whatever it was drawn for.
- **Invented text confirmed by ear** is a possibly invented run whose writer's
  version the maintainer found wrong: the other right, or both wrong. The runs
  heard are drawn from both contenders' together, and a run both wrote at the
  same place counts for both, so each contender's runs are heard in the same
  proportion and the confirmed ones are compared as counted.
- **AssemblyAI's time** runs from the start of the upload to the fetched
  answer. A run interrupted and taken up later counts the pause.
- **The sound** is uploaded as 16 kHz mono FLAC, without the tags or the name
  of the file it comes from: what the transcriber itself works on, and the rate
  AssemblyAI converts every file to.

## Tests

`.venv\Scripts\python -m pytest -q` runs them with the transcriber's own. They
cover the two seams of the spec and the verdict rule; the upload, the deletion
and the transcriber's run are tried on one short recording instead.
