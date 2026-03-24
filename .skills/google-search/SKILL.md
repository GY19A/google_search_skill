---
name: google-search
description: Performs web searches with a resilient Google search workflow using a local helper script and fallback search providers. Use when the user asks to look something up online, find sources, or perform a web search.
---

# Google Search

## Purpose

Use this skill to find current or hard-to-remember information on the web. Prefer the local helper at `.skills/google_Search.py` when you need the repository's search workflow.

## Search Workflow

1. Start with the local helper workflow.
2. Prefer the `requests`-based Google parsing path first.
3. If that fails, fall back to `ddgs`.
4. If that also fails, fall back to `googlesearch-python`.
5. Return concise results with title, URL, and a short snippet.

## Querying

- Keep queries short and specific.
- Use multiple queries when the topic has several names or aliases.
- Prefer English queries unless the user asks otherwise.

## Result Handling

- Deduplicate repeated URLs.
- Prefer authoritative sources first.
- Summarize only the useful part of each result.
- Do not add unnecessary commentary.

## Reliability Notes

- Use a realistic user agent and gentle request pacing.
- Handle missing or blocked results by switching to the fallback providers.
- Keep the search output compact and actionable.

## Script Reference

The helper script is stored at `.skills/google_Search.py`.
