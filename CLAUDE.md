# BRAIN — Personal Knowledge Wiki

This is a persistent, LLM-maintained wiki. Claude Code reads source documents and
incrementally builds a structured, interlinked knowledge base of markdown files.
The human curates sources and asks questions. The LLM does all writing,
cross-referencing, and maintenance. Obsidian is the viewer.

## Directory Structure

- `inbox/` — Immutable source documents. The LLM reads but NEVER modifies these.
  Supported formats: `.txt`, `.md`, `.pdf`, `.html`, `.png`, `.jpg`, `.jpeg`, `.webp`.
  For PDF/HTML, run `python scripts/extract.py <file>` to get a `.extracted.md`
  version. Images are read directly by Claude (vision).
- `brain/` — LLM-generated markdown files. The LLM owns this entirely.
  - `brain/index.md` — Catalog of all pages with one-line summaries, organized by category.
  - `brain/log.md` — Append-only chronological activity log.
  - `brain/projects/` — Notes tied to active projects with a clear outcome or deadline.
  - `brain/areas/` — Notes for ongoing areas of responsibility or long-term interest.
  - `brain/resources/` — Reference material: source summaries, tools, topics, concepts.
  - `brain/archive/` — Inactive or completed notes moved out of the other folders.
- `outputs/` — Saved query results, analyses, generated artifacts.
- `scripts/` — Utility scripts (extraction, etc.).

## Page Conventions

Every brain page uses this format:

```markdown
# Title

> Created: YYYY-MM-DD

Content in plain prose or bullet points.
[[wikilinks]] for all internal references.
```

No YAML frontmatter. No `updated:`, `type:`, `tags:`, or `sources:` fields. Keep notes clean and readable — metadata lives in `index.md`, not in every file.

- **File naming**: `kebab-case.md` (e.g. `spaced-repetition.md`)
- **Internal links**: use Obsidian wikilinks `[[page-name]]`
- **Every page** must link to at least one other brain page
- **Citations**: cite sources inline in prose — `(source: filename.pdf)`
- **Images**: embed with Obsidian syntax `![[image.png]]` when relevant to a page

## PARA Folder Guide

Use this to decide where a new note belongs:

| Folder | Contents | Ask yourself |
|--------|----------|--------------|
| `projects/` | Active work with a defined outcome | Is there a finish line? |
| `areas/` | Ongoing responsibilities or interests with no end date | Am I maintaining this over time? |
| `resources/` | Reference material, source summaries, tools, topics | Would I look this up later? |
| `archive/` | Anything from the above that is no longer active | Is this done or dormant? |

## Workflows

### Ingest

Triggered when the user adds a source to `inbox/` and asks to process it.

1. **Extract** (if needed):
   - PDF or HTML: run `python scripts/extract.py inbox/<file>` to get readable text.
   - Images (`.png`, `.jpg`, `.jpeg`, `.webp`): read directly using vision. No extraction needed.
   - `.txt` or `.md`: read directly.
2. **Read** the source fully.
3. **Discuss** key takeaways with the user. Ask what to emphasize.
4. **Create a source summary** in `brain/resources/<source-name>.md`.
5. **Create or update supporting notes** in the appropriate PARA folder:
   - Ongoing topic or reference → `brain/resources/`
   - Active project context → `brain/projects/`
   - Area of responsibility → `brain/areas/`
   Don't overwrite — integrate new information with existing content.
6. **Cross-reference**: if the source connects, contradicts, or extends existing pages,
   update those pages. Flag contradictions explicitly with a `> [!warning]` callout.
7. **Update** `brain/index.md` with any new pages.
8. **Append** an entry to `brain/log.md`.

### Query

Triggered when the user asks a question.

1. Read `brain/index.md` to identify relevant pages.
2. Read those pages.
3. Synthesize an answer with citations to brain pages and original sources.
4. If the answer is substantial (comparison, analysis, deep question), save it to
   `outputs/` and offer to file it into the brain as a page in the appropriate PARA folder.

### Lint

Triggered when the user asks to health-check the wiki.

1. Identify orphan pages (no inbound links from other pages).
2. Find concepts or entities mentioned across pages but lacking their own page.
3. Flag contradictions between pages.
4. Flag stale claims that newer sources may have superseded.
5. Suggest missing cross-references.
6. Suggest new sources to investigate for gaps in coverage.
7. Log the lint pass in `brain/log.md`.

## Rules

- **NEVER** modify files in `inbox/`. They are the immutable source of truth.
- **ALWAYS** update `brain/index.md` and `brain/log.md` on every ingest. Do this automatically — no confirmation needed, never ask the user for permission to write these two files.
- **INTEGRATE, don't overwrite**. When updating an existing page, preserve existing
  content and weave in new information. Show how the new source adds to, refines,
  or contradicts what was already there.
- **Flag contradictions** explicitly using `> [!warning]` callouts rather than
  silently resolving them. Let the human decide.
- **Keep pages focused**. One topic per page. If a page grows beyond ~300 lines,
  consider splitting it.
- **Prefer many interlinked pages** over few long pages.
- **Log entries** use the format: `## [YYYY-MM-DD] verb | Subject`
  (e.g. `## [2026-04-06] ingest | Article Title`)
