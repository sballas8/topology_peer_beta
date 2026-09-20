# Topology Peer Student v0.13

This version separates course content from the application and persistently records conversations.

## Structure

- `course/course.json` — course identity and tutor version
- `course/homework/` — one editable JSON file per homework set
- `course/assessments.json` — current in-class assessment plan (not shown in the student app)
- `course/prompts/tutor_prompt.txt` — tutor behavior
- `course/conversations/conversations.db` — persistent interaction database
- `course/conversations/schema.sql` — readable database schema

## Research-data design

Every conversation and every message is stored with stable IDs, timestamps, workspace,
homework/problem context where applicable, and tutor version. The prototype student ID is
pseudonymous and contains no name/email.

Important: the current prototype generates its pseudonymous student ID per Streamlit session.
A production deployment should replace this with authentication that supplies a stable
pseudonymous research ID while keeping the identity mapping outside the transcript database.

The live database should be treated as restricted course data. A later research-export process
should de-identify message text before any external sharing.

## Homework included

The package contains the early assignments discussed so far:
- Homework 1: topology construction; metric/topology AI discussion; continuity of `3x+2`;
  smallest topology containing specified sets.
- Homework 2: basis generates a topology; rational-endpoint AI discussion; identity-map
  continuity; continuity checked on basis elements.

`Homework 1, Problem 4` still contains a placeholder for the specific sets A, B, C because
the exact sets were not recoverable from the planning record used to build this version.

The in-class practice and first graded assessment are preserved in `course/assessments.json`.


## Archive test harness

`archive_harness.py` creates a small synthetic archive containing three fake students and six
fake conversations spanning homework and freeform work.

From the project folder:

    python archive_harness.py seed
    python archive_harness.py inspect
    python archive_harness.py clear

`seed` adds fake data to the same `course/conversations/conversations.db` used by the app.
`inspect` prints the archive in a human-readable form.
`clear` removes only records created by the harness.

The fake IDs are intentionally recognizable (`fake_student_*`, `fake_conv_*`, `fake_msg_*`)
so test records can never be confused with real course records.

## v0.7 packaging

This ZIP is intentionally packaged with exactly one top-level folder:
`topology-peer-student-v0_7/`.

The archive harness is directly inside that folder, alongside `app.py`.
All commands in the project documentation assume the terminal is already in the parent
`undergrad_topology` directory and the `topology-peer` virtual environment is active.

From `undergrad_topology`:

    python topology-peer-student-v0_7/archive_harness.py seed
    python topology-peer-student-v0_7/archive_harness.py inspect
    python topology-peer-student-v0_7/archive_harness.py clear
    streamlit run topology-peer-student-v0_7/app.py

## v0.8 synthetic archive stress test

The archive harness can now generate a substantial fake research corpus.

From the parent `undergrad_topology` directory:

    python topology-peer-student-v0_8/archive_harness.py generate
    python topology-peer-student-v0_8/archive_harness.py report
    python topology-peer-student-v0_8/archive_harness.py test
    python topology-peer-student-v0_8/archive_harness.py clear

By default `generate` creates 120 synthetic conversations across 20 pseudonymous students.
You can change the size, for example:

    python topology-peer-student-v0_8/archive_harness.py generate --students 30 --conversations 300

`report` demonstrates useful research-oriented retrieval: workspace counts, assignment/problem
coverage, tutor-version counts, keyword searches, and one student's longitudinal record.

`test` runs structural acceptance checks. `clear` removes only synthetic records.

## v0.10 student navigation

The student-facing selectors now use the hierarchy:

- Mode
- Assignment
- Question

Homework mode shows all three selectors. Conversations mode replaces the assignment/question
selectors with a Conversation selector and previews the original assignment/question or the
opening freeform prompt. Freeform discussion shows only the Mode selector.


## v0.11 course content

Course content is populated through Week 6. Homework 1–5 correspond to Weeks 2–6 and include the weekly AI conversation as an AI-discussion question. The assessment plan includes the Week 2 practice check and graded Week 3–6 checks. Week 1 conversation activities are preserved in `course/activities/week_01.json`.

From the parent `undergrad_topology` directory:

    streamlit run topology-peer-student-v0_11/app.py

## v0.13 transcript export

To make the conversation archive easy to review, v0.13 adds a one-command instructor export.
From the parent `undergrad_topology` directory:

    python topology-peer-student-v0_13/transcript_export.py export

The command creates a timestamped ZIP inside `topology-peer-student-v0_13/exports/` containing:

- `conversations.db` — a consistent SQLite snapshot, useful for systematic queries;
- `transcripts.jsonl` — one complete conversation per line, with metadata and ordered messages;
- `transcripts.txt` — the same archive in a convenient human-readable format;
- `manifest.json` — export metadata and a privacy note.

Synthetic conversations created by the archive harness are excluded by default. To include them:

    python topology-peer-student-v0_13/transcript_export.py export --include-synthetic

The export does not automatically redact message text. Student IDs remain whatever pseudonymous IDs
are stored in the app, but students could type identifying information into messages, so real-course
exports should still be treated as restricted course data.


## v0.14: automatic starts for curated Conversations

Each item under `course/activities/` may now include an optional `initial_prompt`. This is an instructor-only launch instruction. When a student opens a new curated Conversation with this field, Topology Peer automatically generates and stores the first assistant message. The hidden launch instruction is not stored as a student message and is not shown in the transcript. Homework and Freeform discussion continue to wait for the student to speak first.


## v0.15 activity instructions
Curated conversation JSON may include `tutor_instructions`, which are included on every API turn, and `initial_prompt`, which is used only to generate the tutor opening message.


## v0.16: curated Conversation deliverables

Curated Conversation items may include an optional `deliverable` field. When present:

- the deliverable is shown to the student beneath the Conversation prompt;
- it is included in the tutor's persistent instructions on every turn;
- Topology Peer is instructed to make sure the conversation reaches the deliverable;
- the student must write the deliverable in their own words;
- Topology Peer may critique a student draft but must not write, rewrite, or polish it.

Week 4 — Infinite products includes the first configured deliverable.
