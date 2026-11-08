# OrbitFlow synthetic sales-call dataset

This package contains 20 fictional B2B SaaS sales-call transcripts for use in an AI engineering interview case.

Case Instructions:
- `instructions.md`: instructions for the coding task

Supporting Files:
- `manifest.json`: lightweight call metadata and filenames.
- `calls/call-*.txt`: one transcript per call.

## What's in the dataset

The vendor throughout is OrbitFlow, a fictional workflow automation platform.

| Call type | Calls | Notes |
|---|---|---|
| Prospect calls | 001–010 | Discovery, technical discovery, evaluation, security review |
| Renewals | 011–013 | One healthy expansion, one at risk, one renewal with an AI expansion |
| Churn post-mortems | 014–015 | One enterprise loss to a competitor, one small customer that over-bought |
| Cold calls | 016–020 | Hard brush-off, gatekeeper, successful, badly handled, competitive/too-late |

Transcripts range from **2 to 41 minutes** and **23 to 312 turns**. Section order varies by call — some are security-led, some demo-first, some cover pricing in the first five minutes and some never reach it. Not every call covers every topic, which is deliberate.

## File format

Each transcript has a plain-text header, then a `TRANSCRIPT` marker, then one turn per line as `[MM:SS] Speaker Name: text`.

Two header details worth knowing before you write a parser:

- The company field is labelled `PROSPECT:` on calls 001–010 and 016–020, and `CUSTOMER:` on calls 011–015 (existing customers). In `manifest.json` both are carried under the single key `prospect_company`, with `call_type` distinguishing them.
- `manifest.json` also carries `stage`, `duration_minutes`, and the participant list. Participants and durations are consistent with the transcript headers.

The transcripts contain recurring themes, ambiguous statements, inconsistent customer descriptions, different technology stacks, competing products, pricing reactions, security requirements, and varying buying signals. They are written as messy conversation: hesitations, interruptions, sentences broken across turns, crosstalk, `[inaudible]`, `[pause]`, side tangents and rapport-building anecdotes. However, speaker attribution is always correct.

All companies, people, products, and events are fictional.
