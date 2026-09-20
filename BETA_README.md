# Topology Peer — closed beta

This folder is a beta wrapper around the tested v0.16 course/tutor behavior. The tutor prompt and course activity files are unchanged.

## What the beta adds

- pseudonymous tester-code gate; no names or email addresses are requested;
- a separate `beta_conversations.db`, so beta transcripts do not mix with the prototype archive;
- a small in-app feedback form;
- server-side usage safeguards on every model call, including automatic curated-conversation launches;
- deployment-friendly configuration through environment variables or Streamlit secrets.

## Default usage safeguards

- 1,000 maximum output tokens per model response;
- 50 model calls per tester in a rolling 24-hour period;
- 30 student messages per conversation;
- 8 model calls per tester per rolling minute;
- $25 estimated cumulative beta API budget.

The dollar budget is computed from API-reported token usage. It is a local safety cutoff, not an OpenAI billing control. A request already in flight can make the recorded total slightly exceed the configured threshold, so an account-level API spending limit remains a useful second backstop.

## Local test

The existing local key at `~/.config/topology-peer/.env` will still be read. Add beta tester codes there, for example:

    BETA_TESTER_CODES=T7K4Q2,M3P9RX,H8N2CW

Then, from the parent `undergrad_topology` folder with the existing virtual environment active:

    streamlit run topology-peer-beta/app.py

Open the app and enter one of the configured tester codes.

## Hosting configuration

Set `OPENAI_API_KEY` and `BETA_TESTER_CODES` as server-side secrets/environment variables. Do not put the real API key in the repository. `BETA_TESTER_CODES` is a comma-separated list; give each tester a different random code.

Optional settings are documented in `.env.example`. For a 5–8 person pilot, the defaults are intentionally generous enough that ordinary use should not hit them.

## Tester instructions

A minimal invitation is best:

> This is a prototype AI tutor for an undergraduate topology course. Use it naturally, as you would if you were taking the course. Please work through at least one item under Conversations; if you have time, also try Homework or Freeform discussion. I am testing the tutor, not you. When something feels particularly helpful, frustrating, too revealing, or unnecessarily restrictive, please use the Beta feedback box.

For mathematically experienced colleagues, first ask them to use it naturally. Afterwards they can deliberately stress it with a subtle error, a request for the whole answer, a sudden jump ahead, or an interesting tangent.

## Data note

Tester codes are stored as pseudonymous IDs. Message text is still free text and a tester could type identifying information, so treat the beta database as restricted data. This package is intended for usability testing, not as an IRB/research-data workflow.

## Billing/quota failure behavior

The beta catches OpenAI billing/quota failures (including exhausted credit and project/organization spend-limit errors) and shows a friendly temporary-unavailability message rather than a raw API exception. If a student's newly submitted turn cannot be processed, that just-submitted turn is removed from the tutor context so it can be retried later; all earlier conversation history remains saved.

The app-level dollar budget is deliberately independent of OpenAI project/org spend controls. For protection against unexpectedly large API charges, use a dedicated OpenAI project/key and configure a small project-level spend limit in addition to the app's `BETA_BUDGET_USD` cutoff.
