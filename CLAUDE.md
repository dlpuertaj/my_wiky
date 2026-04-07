# BRAIN — Personal Knowledge Wiki

This is a persistent, LLM-maintained wiki. Claude Code reads raw sources and
incrementally builds a structured, interlinked knowledge base of markdown files.
The human curates sources and asks questions. The LLM does all writing,
cross-referencing, and maintenance. Obsidian is the viewer.

## Directory Structure

- `raw/` — Immutable source documents. The LLM reads but NEVER modifies these.
  Supported formats: `.txt`, `.md`, `.pdf`, `.html`, `.png`, `.jpg`, `.jpeg`, `.webp`.
  For PDF/HTML, run `python scripts/extract.py <file>` to get a `.extracted.md`
  version. Images are read directly by Claude (vision).
- `wiki/` — LLM-generated markdown files. The LLM owns this entirely.
  - `wiki/index.md` — Catalog of all pages with one-line summaries, organized by category.
  - `wiki/log.md` — Append-only chronological activity log.
  - `wiki/sources/` — One summary page per ingested source.
  - `wiki/entities/` — Pages for people, organizations, tools, places, products.
  - `wiki/concepts/` — Pages for ideas, frameworks, theories, methods.
  - `wiki/maps/` — Synthesis pages, comparisons, overviews, timelines.
- `outputs/` — Saved query results, analyses, generated artifacts.
- `scripts/` — Utility scripts (extraction, etc.).

## Page Conventions

Every wiki page uses this frontmatter:

```yaml
---
title: Page Title
type: source | entity | concept | map
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [filename1.pdf, filename2.md]
tags: [tag1, tag2]
---
```

- **File naming**: `kebab-case.md` (e.g. `spaced-repetition.md`)
- **Internal links**: use Obsidian wikilinks `[[page-name]]`
- **Every page** must link to at least one other wiki page
- **Citations**: every claim from a source should cite it — `(source: filename.pdf)`
- **Images**: embed with Obsidian syntax `![[image.png]]` when relevant to a page

## Workflows

### Ingest

Triggered when the user adds a source to `raw/` and asks to process it.

1. **Extract** (if needed):
   - PDF or HTML: run `python scripts/extract.py raw/<file>` to get readable text.
   - Images (`.png`, `.jpg`, `.jpeg`, `.webp`): read directly using vision. No extraction needed.
   - `.txt` or `.md`: read directly.
2. **Read** the source fully.
3. **Discuss** key takeaways with the user. Ask what to emphasize.
4. **Create source summary** in `wiki/sources/<source-name>.md`.
5. **Create or update entity pages** in `wiki/entities/` for each notable entity.
   Don't overwrite — integrate new information with existing content.
6. **Create or update concept pages** in `wiki/concepts/` for each notable concept.
7. **Cross-reference**: if the source connects, contradicts, or extends existing pages,
   update those pages. Flag contradictions explicitly with a `> [!warning]` callout.
8. **Update** `wiki/index.md` with any new pages.
9. **Append** an entry to `wiki/log.md`.

### Query

Triggered when the user asks a question.

1. Read `wiki/index.md` to identify relevant pages.
2. Read those pages.
3. Synthesize an answer with citations to wiki pages and original sources.
4. If the answer is substantial (comparison, analysis, deep question), save it to
   `outputs/` and offer to file it into the wiki as a map page in `wiki/maps/`.

### Lint

Triggered when the user asks to health-check the wiki.

1. Identify orphan pages (no inbound links from other pages).
2. Find concepts or entities mentioned across pages but lacking their own page.
3. Flag contradictions between pages.
4. Flag stale claims that newer sources may have superseded.
5. Suggest missing cross-references.
6. Suggest new sources to investigate for gaps in coverage.
7. Log the lint pass in `wiki/log.md`.

## Rules

- **NEVER** modify files in `raw/`. They are the immutable source of truth.
- **ALWAYS** update `index.md` and `log.md` on every ingest.
- **INTEGRATE, don't overwrite**. When updating an existing page, preserve existing
  content and weave in new information. Show how the new source adds to, refines,
  or contradicts what was already there.
- **Flag contradictions** explicitly using `> [!warning]` callouts rather than
  silently resolving them. Let the human decide.
- **Keep pages focused**. One entity or concept per page. If a page grows beyond
  ~300 lines, consider splitting it.
- **Prefer many interlinked pages** over few long pages.
- **Log entries** use the format: `## [YYYY-MM-DD] verb | Subject`
  (e.g. `## [2026-04-06] ingest | Article Title`)
