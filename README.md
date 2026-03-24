# Google Search Skill Bundle

This repository contains a Cursor skill bundle for web search workflows.

## Contents

- `.skills/google-search/SKILL.md` - the standard Cursor skill definition
- `.skills/google_Search.py` - the local search helper used by the skill

## What it does

The skill provides a resilient Google search workflow with fallbacks for:

1. direct Google HTML parsing
2. `ddgs`
3. `googlesearch-python`
4. headless Chrome rendering for JavaScript-heavy pages

## Usage

Place the `.skills` directory in a Cursor project or import it into your own skill setup.
The main entry point is the `google-search` skill, which references the helper script in `.skills/google_Search.py`.

## Notes

- The repository is intentionally small and contains only the skill bundle.
- The helper is designed to be conservative and fall back when Google blocks direct requests.
