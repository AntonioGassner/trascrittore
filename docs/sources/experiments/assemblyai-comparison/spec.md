# Trial: is AssemblyAI an upgrade over the transcriber's own transcription?

Written on 2026-11-13 as experiment material. It records how the trial is to be
run and judged; it adopts no decision for the transcriber.

> Contradicts [ADR 0001](../../../adr/0001-transcription-stays-on-the-pc.md)
> for the recordings of the trial only: their sound is sent to an external
> transcription service. Worth doing because the ADR was taken without knowing
> how much better such a service transcribes, and the trial measures exactly
> that. The transcriber itself does not change, and the ADR stands until the
> maintainer decides otherwise with the results in hand.

## Problem Statement

The maintainer reads many transcripts and finds their quality middling: names
and technical terms come out as misheard words, sentences are cut where the
speaker changes, some speech is missing without any sign, and some passages are
unintelligible. The transcriber writes its words with Whisper large-v3 through
whisperX, which is no longer the state of the art. AssemblyAI is recommended as
better, but the only figures available are the vendor's own, mostly for
English. Nobody knows whether it transcribes the maintainer's recordings, which
are Italian work calls and in-person conversations full of names and technical
terms, better than the transcriber does today, nor by how much.

Switching has a price that only a clear gain would justify: AssemblyAI runs
only as a service, so recordings and voices would leave the PC, against ADR
0001, and every hour of recording would cost money.

## Solution

A one-off trial on recordings that are already on the maintainer's PC and
already have a curated transcript. Each recording of the trial is transcribed
twice, by today's transcriber and by AssemblyAI, and the two transcripts are
judged in two ways:

- **Against the curated transcript**, automatically: how many words differ,
  how many of the misheard words the curation corrected come out right, how
  much of the speech the curation found missing is there, and how many words
  are given to the right speaker.
- **Against the recording itself**, by ear: the maintainer hears a sample of
  the passages on which the two transcripts disagree and says which one is
  right, without knowing which system wrote which.

The second judgement exists because the first is tilted. Every curated
transcript was made by correcting a transcript of the transcriber, so wherever
nobody noticed an error, the curated transcript still says what the transcriber
heard, and AssemblyAI is marked wrong for hearing it right.

The trial ends with a short report: the scores, the hours and money spent, and
one of three verdicts fixed before the first run: upgrade, no clear difference,
or worse. The report says nothing about whether to switch; that is a later
decision about ADR 0001.

In this document a **curated transcript** is the copy of a transcript that an
agent tidied and corrected with the maintainer, who confirmed its doubtful
passages. A **contender** is one of the two systems under trial. The **trial
set** is the recordings the trial uses. The **blind comparison** is the
judgement by ear.

## User Stories

1. As the maintainer, I want one verdict among upgrade, no clear difference and
   worse, so that I know whether reopening ADR 0001 is worth my time.
2. As the maintainer, I want the rule for the verdict written before any
   recording is transcribed, so that the result cannot bend the rule.
3. As the maintainer, I want the trial to use recordings I already have, so
   that I record nothing new for it.
4. As the maintainer, I want my curated transcripts used as the reference, so
   that the corrections I already confirmed are what a good transcript is
   measured against.
5. As the maintainer, I want to see and approve the list of recordings before
   any of them is uploaded, so that no recording leaves my PC without my saying
   so.
6. As the maintainer, I want to leave out any recording whose speakers I would
   not want sent to a third party, so that the trial respects the people in it.
7. As a person heard in a recording, I want only the sound to be uploaded, never
   the video, so that my face and my screen stay on the PC.
8. As a person heard in a recording, I want what was uploaded deleted from
   AssemblyAI once its transcript is fetched, so that my voice does not stay
   with a third party.
9. As the maintainer, I want AssemblyAI's terms on keeping uploads and on
   training with them read and shown to me before the first upload, so that I
   approve the list knowing them.
10. As the maintainer, I want the uploads to go to AssemblyAI's European
    endpoint, so that the recordings stay in the EU.
11. As the maintainer, I want the trial set to hold both remote calls and
    in-person recordings, so that the verdict covers the clean sound and the
    difficult one.
12. As the maintainer, I want every recording of the trial transcribed again by
    today's transcriber, so that AssemblyAI is compared with what I would get
    today and not with transcripts made by older versions.
13. As the maintainer, I want my existing transcripts and the folders they are
    in left exactly as they are, so that the trial disturbs none of my files.
14. As the maintainer, I want the share of differing words against the curated
    transcript for each contender, so that I have one overall figure per
    recording and for the whole set.
15. As the maintainer, I want the stored transcript, the one the curation
    started from, scored in the same way, so that I can see how far a
    transcript sits from its own curated copy and read the other figures
    against that.
16. As the maintainer, I want to know how many of the misheard words the
    curation corrected each contender writes correctly, so that I see whether
    names and technical terms improve.
17. As the maintainer, I want to know how many of the stretches the curation
    marked as not transcribed hold words in each contender's transcript, so
    that I see whether less speech goes missing.
18. As the maintainer, I want the same for the passages the curation marked as
    unintelligible or uncertain, so that I see whether difficult passages
    become readable.
19. As the maintainer, I want words that a contender writes where the curated
    transcript has such a mark not counted as errors, so that a contender is
    not punished for hearing what the transcriber missed.
20. As the maintainer, I want to know how many words each contender gives to
    the right speaker, so that I see whether sentences are still cut and
    swapped where the speaker changes.
21. As the maintainer, I want to know how many speakers each contender found
    against how many there were, so that I see whether voices are merged or
    split.
22. As the maintainer, I want long runs of words that appear in one contender
    only listed as possibly invented, so that I can hear whether the system
    made them up.
23. As the maintainer, I want to judge by ear a sample of the passages where
    the contenders disagree, so that the verdict does not rest on a reference
    made from one contender's output.
24. As the maintainer, I want the two versions of each passage shown in the
    same plain form and in random order, so that I cannot tell which contender
    wrote which.
25. As the maintainer, I want to hear each passage with one command or one
    click, so that judging sixty passages takes well under an hour.
26. As the maintainer, I want to answer first, second, both fine, both wrong or
    cannot tell, so that I am never forced to pick a winner.
27. As the maintainer, I want which contender wrote which version revealed
    only after I judged the last passage, so that early answers do not colour
    later ones.
28. As the maintainer, I want to stop the blind comparison and resume it later,
    so that I can fit it around my work.
29. As the maintainer, I want AssemblyAI tried once plainly and once with a
    list of names and terms, so that I see what its vocabulary feature adds.
30. As the maintainer, I want the verdict to rest on the plain run, so that it
    does not depend on a list that was itself improved by the curation.
31. As the maintainer, I want the time each contender took per recording, so
    that I know how long I would wait.
32. As the maintainer, I want the money AssemblyAI charged for the trial and
    its price per hour of recording, so that I can estimate a year of use.
33. As the maintainer, I want every failed upload or failed transcription
    reported, so that reliability is part of the picture.
34. As the maintainer, I want the report to give scores per recording and
    separately for remote calls and in-person recordings, so that one long
    recording does not hide the others.
35. As the maintainer, I want the report to state the known tilt of each
    measure, so that I read no figure as more than it is.
36. As the maintainer, I want the report to contain no speech, no names and no
    recording names, so that it can sit in a public repository.
37. As the maintainer, I want everything else the trial produces kept outside
    the repository, so that no recording, transcript or voice enters it.
38. As the maintainer, I want the AssemblyAI key read from the file that
    already holds my secrets and never printed, so that it does not leak.
39. As an agent running the trial, I want the upload to refuse any recording
    that is not on the approved list, so that a wrong path cannot send a
    recording out.
40. As an agent running the trial, I want AssemblyAI's full answer for each
    recording saved as it arrived, so that a change in the scoring never needs
    a second upload.
41. As an agent running the trial, I want each step to skip the recordings it
    already finished, so that an interrupted run resumes without paying twice.
42. As an agent running the trial, I want both contenders' transcripts in the
    one form the transcriber already writes, so that one scorer and the
    existing passage player serve both.
43. As an agent running the trial, I want to try the whole path on one short
    recording first, so that faults show before the full set is uploaded.
44. As the maintainer, I want the trial to add nothing to the transcriber that
    people install, so that the trial cannot change what they get.
45. As a developer reading the repository later, I want the trial's method and
    its result kept with the experiment material, so that I know why the
    transcriber does or does not use an external service.

## Implementation Decisions

### The trial set

- A recording is eligible when it is still on the PC and has a finished
  curated transcript made from a transcript of the transcriber. On 2026-11-13
  that is about 19 curated transcripts out of 23 transcribed recordings,
  roughly 22 hours in all; three more curated transcripts are still drafts and
  stay out.
- The whole eligible set is proposed, since the money is small (see below). The
  maintainer strikes what must not leave the PC. The trial is not run with
  fewer than 6 recordings or fewer than 2 in-person ones.
- The trial set is a list, kept outside the repository, that pairs each
  recording with its curated transcript and its stored transcript, says
  whether it is a remote call or in person, and carries the maintainer's
  approval. Every step reads this list and nothing else.

### The contenders

- **The transcriber** as it is on the main branch on the day of the run,
  through its own command line, with its default settings and without the
  number of speakers. Its transcripts go to a folder of the trial, so that the
  recordings do not move and the existing transcripts are not overwritten.
- **AssemblyAI**, model `universal-3-5-pro`, pre-recorded transcription, Italian
  stated as the language, speaker labels on, no number of speakers. A second run
  adds key terms: the names in the voice library and the terms of the glossary
  of the recording's client, as they stand. Since those glossaries were updated
  while curating these same recordings, the second run flatters AssemblyAI and
  is reported apart.
- AssemblyAI's answer is converted into the transcript form the transcriber
  writes: speakers, turns and segments with their times, a segment being what
  the glossary says it is. Its speakers stay anonymous; recognition is not run
  on them.

### Sending recordings out

- Only the sound of a recording is uploaded, extracted on the PC as one mono
  file.
- Uploads go to the European endpoint. The upload step takes recordings only
  from the approved list.
- Before the first upload the agent reads AssemblyAI's terms on how long
  uploads and transcripts are kept and whether they are used for training, and
  the maintainer approves the list after seeing them. The pages read on
  2026-11-13 stated neither.
- When an answer has been fetched and saved, the transcript is deleted from
  AssemblyAI, and the report says whether every deletion succeeded.
- The key lives in the ignored file that already holds the Hugging Face token.

### Scoring against the curated transcript

- A curated transcript is tidied speech: fillers, stutters and false starts
  are gone, turns are split and merged, and sentences are moved back to the
  speaker who said them. So both sides are normalized in the same way before
  comparing: lower case, no punctuation, one spelling for accents and
  apostrophes, fillers and immediate repetitions removed. The words are
  compared over the whole recording, whoever said them, so that moved turn
  boundaries do not count.
- **Differing words**: the word error rate of each contender against the
  curated transcript. Its absolute value means little after this
  normalization; what counts is the gap between the contenders, read against
  the stored transcript's own score.
- **Marked passages**: the curated transcript marks speech that was not
  transcribed, passages nobody could make out, and words left uncertain. Words
  a contender writes at a mark are not errors. For each mark the scorer says
  whether the contender has words there, and those passages go to the blind
  comparison to tell real speech from invented text.
- **Corrected words**: the words that differ between the stored transcript and
  the curated transcript, restricted to substitutions of content words, are
  the misheard words the curation corrected. For each, the scorer says whether
  each contender wrote the corrected form. This measure only looks where the
  transcriber of the time was wrong, so it can show AssemblyAI gaining but not
  losing; the other measures cover the losses.
- **Speakers**: each contender's speakers are paired with the curated
  transcript's speakers by greatest overlap, whatever their labels. The score
  is the share of matched words given to the right speaker, with the number of
  speakers found beside the number there were.
- **Possibly invented text**: runs of several words in a row that a contender
  has and the curated transcript has not, away from any mark. They are listed
  and join the blind comparison.

### The blind comparison

- 60 passages, drawn at random from the places where the two contenders'
  normalized words differ, spread over the recordings, with at least 15 from
  in-person recordings. The passages at marks and the possibly invented runs
  are added to these when they are few, sampled when they are many.
- Each passage is a stretch of 10 to 20 seconds around the difference. The
  maintainer hears it from the recording and sees both versions in the same
  plain form, numbered 1 and 2 in random order.
- Answers: 1 is right, 2 is right, both fine, both wrong, cannot tell. They are
  saved one at a time, and the key that says who wrote what stays closed until
  the last answer.
- The plain AssemblyAI run is the one compared. About 45 minutes of the
  maintainer's time.

### The verdict

Fixed here, before any run. With W the passages where AssemblyAI was right and
the transcriber wrong, and L the opposite:

- **Upgrade**: W + L is at least 30, W is at least twice L, AssemblyAI's word
  error rate over the whole set is not higher than the transcriber's, its
  share of words given to the right speaker is not more than 2 points lower,
  and it has no more passages of invented text confirmed by ear.
- **Worse**: L is greater than W, or AssemblyAI has more confirmed invented
  text and W is less than twice L.
- **No clear difference**: anything else, including fewer than 30 decided
  passages. For the question of leaving the PC, this counts as staying.

### Cost and where things live

- Prices read on AssemblyAI's pricing page on 2026-11-13: $0.21 per hour of
  recording, $0.02 more for speaker labels, $0.05 more for key terms. Both runs
  over 22 hours come to about $11, inside the $50 of credit given on signing
  up. The report states what was actually charged.
- The trial's code and the final report sit with the experiment material. The
  trial list, the uploaded sound files, AssemblyAI's answers, both contenders'
  transcripts, the per-passage tables and the blind comparison's answers sit in
  one folder outside the repository.
- The trial changes nothing in the transcriber: no setting, no command, no
  dependency of the image. What the trial needs beyond the transcriber's own
  dependencies is installed for development only.

## Testing Decisions

- A good test here gives made-up input in at one of the two seams below and
  checks what comes out, with no knowledge of how the result is computed. No
  test uses a real recording, transcript or name.
- **Seam 1, the transcript form.** The form the transcriber already writes is
  the only thing the scorer and the passage player read. The conversion of an
  AssemblyAI answer into it is tested with a small invented answer: speakers
  become anonymous speakers, turns follow speaker changes, segments carry the
  right times, an answer without speech gives an empty transcript.
- **Seam 2, the scorer.** A curated transcript and a transcript go in, the
  scores come out. Tested with short invented pairs, one behaviour each:
  punctuation, case and fillers change nothing; a moved turn boundary changes
  nothing in the word score and does change the speaker score; words written
  at a mark are not errors and are reported as recovered; a corrected word
  counts only when the corrected form is written; swapped speaker labels do
  not lower the speaker score; a long extra run is listed as possibly
  invented.
- The verdict rule is tested as a table of counts and expected verdicts,
  including the edges: exactly 30 decided passages, W exactly twice L.
- The upload, the deletion and the transcriber's own run are not tested
  automatically. They are exercised by running the whole path on one short
  recording before the full set.
- Prior art: the tests of transcript rendering, of transcript cleaning and of
  repetition loops, which build small transcripts by hand and check the result.

## Out of Scope

- Deciding whether the transcriber switches to AssemblyAI, and any change to
  ADR 0001 or to the promise that processing stays on the PC.
- Any change to the transcriber: an AssemblyAI mode, a setting, a command.
- Recognition and naming on AssemblyAI's speakers. Whether its speaker
  stretches serve voiceprints as well as today's is a question for after an
  upgrade verdict.
- Other services and newer models that run on the PC. The same trial set and
  scorer can judge them later; nothing here is built for it in advance.
- AssemblyAI's own speaker naming, summaries, translation and live
  transcription.
- Punctuation and readability, which the normalization removes on purpose.
- Recordings in other languages.
- Correcting or extending the curated transcripts for the trial.

## Further Notes

- **The tilt, in one place.** The word error rate favours the transcriber,
  because the curated transcript inherits its wording, its numbers written as
  words or digits, and its unnoticed errors. The corrected-words measure
  favours AssemblyAI, because it looks only where the transcriber failed. The
  blind comparison favours neither, which is why the verdict leans on it.
- Two recordings also have a transcript made by Google Meet. It is not used:
  the trial has two contenders.
- The stored transcripts were made by several versions of the transcriber, and
  none of them carries the warnings today's version writes about looping or
  unaligned stretches. This is why the transcriber's contender is a fresh run.
- One in-person recording lasts four hours and holds most of the passages
  marked unintelligible. Scores are given per recording so that it does not
  decide the totals alone.
- "Curated transcript" is not in the glossary. It names something made outside
  the transcriber, by a skill of the maintainer's, so it is defined here only.
- AssemblyAI facts in this document come from its product, pricing and
  documentation pages as read on 2026-11-13. Whether it offers a deployment on
  the customer's own machines could not be confirmed from them.
