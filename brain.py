#!/usr/bin/env python3
"""
BRAIN Agent — Ollama-powered wiki maintenance agent.

Usage:
    python brain.py ingest raw/document.pdf
    python brain.py query "What is spaced repetition?"
    python brain.py lint

Dependencies:
    pip install requests pdfplumber beautifulsoup4
"""

import argparse
import json
import sys
import re
from datetime import date
from pathlib import Path

import requests

# ── Configuration ───────────────────────────────────────────────────────

MODEL = "qwen3.5:4b"
OLLAMA_URL = "http://localhost:11434"
WIKI_DIR = Path("wiki")
RAW_DIR = Path("raw")
OUTPUTS_DIR = Path("outputs")

WIKI_CONVENTIONS = """
You maintain a personal knowledge wiki in markdown. Follow these conventions:

Page frontmatter format:
---
title: Page Title
type: source | entity | concept | map
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [filename1.pdf]
tags: [tag1, tag2]
---

Rules:
- Use Obsidian wikilinks in kebab-case ONLY: [[spaced-repetition]], [[piotr-wozniak]]
- NEVER link to [[Wiki Index]], [[index]], or [[log]] — those are not wiki pages
- ONLY link to pages that exist in the "Existing pages" list provided, or to pages being created in this session
- Cite sources: (source: filename.pdf)
- Every page must link to at least one other wiki page
- Flag contradictions with > [!warning] callouts
- Keep pages focused — one entity or concept per page
- Be concise and factual
- Do NOT invent facts not present in the source
- Output raw markdown directly — no code fences wrapping the page
""".strip()


# ── Ollama Client ───────────────────────────────────────────────────────

def _clean_output(text):
    """Strip thinking artifacts and stray code fences from model output."""
    # Remove <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</think>\s*", "", text)
    # Remove wrapping ```markdown ... ``` if the entire output is wrapped
    stripped = text.strip()
    if stripped.startswith("```markdown") and stripped.endswith("```"):
        text = stripped[len("```markdown"):].rstrip("`").strip()
    elif stripped.startswith("```yaml") and stripped.endswith("```"):
        text = stripped[len("```yaml"):].rstrip("`").strip()
    elif stripped.startswith("```") and stripped.endswith("```"):
        first_newline = stripped.index("\n") if "\n" in stripped else 3
        text = stripped[first_newline + 1:].rstrip("`").strip()
    return text.strip()


def _normalize_wikilinks(text, known_slugs):
    """Normalize all [[wikilinks]] to kebab-case and remove links to non-page targets."""
    def replace_link(match):
        original = match.group(1)
        slug = slugify(original)
        # Remove links to index, log, or other non-page targets
        if slug in ("wiki-index", "index", "log", "entities", "concepts", "sources", "maps", ""):
            return original  # Return as plain text, not a link
        return f"[[{slug}]]"

    return re.sub(r"\[\[([^\]]+)\]\]", replace_link, text)


def _build_payload(messages, stream=False, json_format=False):
    """Build Ollama API payload with thinking disabled."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": stream,
        "think": False,
    }
    if json_format:
        payload["format"] = "json"
    return payload


def ollama_chat(messages, stream=True):
    """Send a chat request to Ollama. Streams to terminal and returns full text."""
    payload = _build_payload(messages, stream=stream)

    if stream:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=600
        )
        response.raise_for_status()
        full_text = []
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    print(content, end="", flush=True)
                    full_text.append(content)
                if data.get("done"):
                    break
        print()
        result = _clean_output("".join(full_text))

        # Retry once if output is empty
        if not result.strip():
            print("  (empty response, retrying...)")
            return ollama_chat(messages, stream=False)

        return result
    else:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat", json=payload, timeout=600
        )
        response.raise_for_status()
        return _clean_output(response.json()["message"]["content"])


def ollama_json(messages):
    """Send a chat request expecting JSON output (no streaming)."""
    payload = _build_payload(messages, json_format=True)
    print("  (generating...)", flush=True)
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
    response.raise_for_status()
    text = response.json()["message"]["content"]
    # Clean any residual thinking artifacts
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"</think>\s*", "", text)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        print(f"\nWarning: Could not parse JSON from model response.")
        print(f"Raw response: {text[:500]}")
        return {}


# ── Wiki Helpers ────────────────────────────────────────────────────────

def slugify(name):
    """Convert a name to kebab-case filename."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def read_source(source_path):
    """Read a source file, preferring extracted version. Returns (text, filename)."""
    extracted = source_path.with_suffix(source_path.suffix + ".extracted.md")
    if extracted.exists():
        return extracted.read_text(encoding="utf-8"), source_path.name

    ext = source_path.suffix.lower()

    if ext in (".txt", ".md"):
        return source_path.read_text(encoding="utf-8"), source_path.name

    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        print("Error: Image files require a vision model.")
        print("Use Claude Code for images, or describe the content in a .txt file.")
        sys.exit(1)

    if ext in (".pdf", ".html", ".htm"):
        print(f"No extracted version found. Run extraction first:")
        print(f"  python scripts/extract.py {source_path}")
        sys.exit(1)

    print(f"Error: unsupported format '{ext}'")
    sys.exit(1)


def read_index():
    """Read the wiki index."""
    path = WIKI_DIR / "index.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def get_all_page_slugs():
    """Get a set of all existing wiki page slugs."""
    slugs = set()
    for subdir in ("sources", "entities", "concepts", "maps"):
        dir_path = WIKI_DIR / subdir
        if dir_path.exists():
            for f in dir_path.glob("*.md"):
                slugs.add(f.stem)
    return slugs


def read_wiki_page(slug):
    """Try to find and read a wiki page by slug. Returns content or None."""
    for subdir in ("entities", "concepts", "sources", "maps"):
        path = WIKI_DIR / subdir / f"{slug}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def write_page(subdir, slug, content, known_slugs=None):
    """Write a wiki page. Normalizes wikilinks before writing."""
    if known_slugs:
        content = _normalize_wikilinks(content, known_slugs)
    path = WIKI_DIR / subdir / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  wrote: {path}")


def update_index(new_pages):
    """Update wiki/index.md with new pages."""
    index_path = WIKI_DIR / "index.md"
    content = index_path.read_text(encoding="utf-8") if index_path.exists() else "# Wiki Index\n"

    for page in new_pages:
        entry = f"- [[{page['slug']}]] — {page['summary']}"

        if f"[[{page['slug']}]]" in content:
            continue

        for placeholder in [
            "_No sources ingested yet._",
            "_No entity pages yet._",
            "_No concept pages yet._",
            "_No synthesis pages yet._",
        ]:
            content = content.replace(placeholder, "")

        section = f"## {page['section']}"
        if section in content:
            idx = content.index(section) + len(section)
            content = content[:idx] + f"\n{entry}" + content[idx:]
        else:
            content += f"\n\n{section}\n{entry}"

    index_path.write_text(content, encoding="utf-8")
    print(f"  updated: {index_path}")


def append_log(verb, subject, details=""):
    """Append an entry to wiki/log.md."""
    log_path = WIKI_DIR / "log.md"
    today = date.today().isoformat()
    entry = f"\n## [{today}] {verb} | {subject}\n\n{details}\n"

    content = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Wiki Log\n"
    content += entry
    log_path.write_text(content, encoding="utf-8")
    print(f"  updated: {log_path}")


def format_page_list(slugs):
    """Format a list of slugs as a string for prompts."""
    if not slugs:
        return "No existing pages yet."
    return ", ".join(f"[[{s}]]" for s in sorted(slugs))


# ── Ingest ──────────────────────────────────────────────────────────────

def cmd_ingest(source_path):
    """Interactive ingest workflow."""
    print(f"\n--- Reading source: {source_path}")
    source_text, source_filename = read_source(source_path)

    # Truncate for LLM context
    max_chars = 12000
    truncated = len(source_text) > max_chars
    source_for_llm = source_text[:max_chars] if truncated else source_text
    if truncated:
        source_for_llm += "\n\n[... truncated ...]"
        print(f"  ({len(source_text)} chars, truncated to {max_chars} for analysis)")

    # Step 1: Analyze source
    print(f"\n--- Analyzing source...")

    analysis = ollama_json([
        {
            "role": "system",
            "content": (
                "You analyze source documents. Return a JSON object with:\n"
                '- "summary": 2-3 sentence summary (string)\n'
                '- "key_takeaways": 3-7 key points (list of strings)\n'
                '- "entities": notable people/orgs/tools/places '
                '(list of {"name": "...", "description": "one line"})\n'
                '- "concepts": notable ideas/frameworks/methods '
                '(list of {"name": "...", "description": "one line"})\n'
                '- "tags": 3-5 tags (list of strings)\n'
                "\nReturn ONLY valid JSON. Do NOT invent facts not in the source."
            ),
        },
        {
            "role": "user",
            "content": f"Analyze this source:\n\nFilename: {source_filename}\n\n{source_for_llm}",
        },
    ])

    # Display analysis
    print(f"\n{'='*60}")
    print(f"Summary: {analysis.get('summary', 'N/A')}")
    print(f"\nKey Takeaways:")
    for i, t in enumerate(analysis.get("key_takeaways", []), 1):
        print(f"  {i}. {t}")
    entities = analysis.get("entities", [])
    concepts = analysis.get("concepts", [])
    print(f"\nEntities: {', '.join(e['name'] for e in entities) or 'none'}")
    print(f"Concepts: {', '.join(c['name'] for c in concepts) or 'none'}")
    print(f"{'='*60}")

    # Step 2: Ask user for emphasis
    print(f"\nWhat would you like to emphasize? (Enter to accept defaults)")
    emphasis = input("> ").strip()
    if not emphasis:
        emphasis = "No special emphasis — balanced coverage."

    # Step 3: Collect existing pages + pages that will be created
    existing_slugs = get_all_page_slugs()
    source_slug = slugify(Path(source_filename).stem)
    today = date.today().isoformat()

    # Build the full set of page slugs (existing + to be created)
    all_slugs = set(existing_slugs)
    all_slugs.add(source_slug)
    for e in entities:
        all_slugs.add(slugify(e["name"]))
    for c in concepts:
        all_slugs.add(slugify(c["name"]))

    pages_list = format_page_list(all_slugs)

    # Step 4: Generate source summary page
    print(f"\n--- Generating source summary...")
    source_page = ollama_chat([
        {
            "role": "system",
            "content": (
                f"{WIKI_CONVENTIONS}\n\n"
                "Generate a wiki source summary page. Output raw markdown with "
                "YAML frontmatter. Include key takeaways and [[wikilinks]] to "
                "entity and concept pages.\n\n"
                f"Existing pages you can link to: {pages_list}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Create a source summary page.\n\n"
                f"Filename: {source_filename}\n"
                f"Date: {today}\n"
                f"User emphasis: {emphasis}\n\n"
                f"Analysis:\n{json.dumps(analysis, indent=2)}\n\n"
                f"Source text:\n{source_for_llm[:4000]}"
            ),
        },
    ])

    write_page("sources", source_slug, source_page, all_slugs)
    new_pages = [
        {"slug": source_slug, "summary": analysis.get("summary", "")[:80], "section": "Sources"}
    ]

    # Step 5: Generate entity pages
    for entity in entities:
        slug = slugify(entity["name"])
        existing = read_wiki_page(slug)

        action = "Updating" if existing else "Creating"
        print(f"\n--- {action} entity: {entity['name']}...")

        if existing:
            prompt = (
                f"Update this existing entity page with new information from "
                f"'{source_filename}'.\n\n"
                f"Existing page:\n{existing}\n\n"
                f"New information: {entity['description']}\n"
                f"User emphasis: {emphasis}\n"
                f"Today: {today}\n\n"
                "Integrate new info — don't overwrite existing content. "
                "Add the new source to the sources list in frontmatter."
            )
        else:
            prompt = (
                f"Create a new entity page for: {entity['name']}\n\n"
                f"Description from source: {entity['description']}\n"
                f"Source: {source_filename}\n"
                f"Date: {today}\n"
                f"User emphasis: {emphasis}"
            )

        page = ollama_chat([
            {
                "role": "system",
                "content": (
                    f"{WIKI_CONVENTIONS}\n\n"
                    "Generate a wiki entity page. Output raw markdown with "
                    "YAML frontmatter (type: entity). Include [[wikilinks]] to related pages.\n\n"
                    f"Existing pages you can link to: {pages_list}"
                ),
            },
            {"role": "user", "content": prompt},
        ])

        write_page("entities", slug, page, all_slugs)
        if not existing:
            new_pages.append(
                {"slug": slug, "summary": entity["description"][:80], "section": "Entities"}
            )

    # Step 6: Generate concept pages
    for concept in concepts:
        slug = slugify(concept["name"])
        existing = read_wiki_page(slug)

        action = "Updating" if existing else "Creating"
        print(f"\n--- {action} concept: {concept['name']}...")

        if existing:
            prompt = (
                f"Update this existing concept page with new information from "
                f"'{source_filename}'.\n\n"
                f"Existing page:\n{existing}\n\n"
                f"New information: {concept['description']}\n"
                f"User emphasis: {emphasis}\n"
                f"Today: {today}\n\n"
                "Integrate new info — don't overwrite existing content. "
                "Add the new source to the sources list in frontmatter."
            )
        else:
            prompt = (
                f"Create a new concept page for: {concept['name']}\n\n"
                f"Description from source: {concept['description']}\n"
                f"Source: {source_filename}\n"
                f"Date: {today}\n"
                f"User emphasis: {emphasis}"
            )

        page = ollama_chat([
            {
                "role": "system",
                "content": (
                    f"{WIKI_CONVENTIONS}\n\n"
                    "Generate a wiki concept page. Output raw markdown with "
                    "YAML frontmatter (type: concept). Include [[wikilinks]] to related pages.\n\n"
                    f"Existing pages you can link to: {pages_list}"
                ),
            },
            {"role": "user", "content": prompt},
        ])

        write_page("concepts", slug, page, all_slugs)
        if not existing:
            new_pages.append(
                {"slug": slug, "summary": concept["description"][:80], "section": "Concepts"}
            )

    # Step 7: Update index and log
    print(f"\n--- Updating index and log...")
    update_index(new_pages)

    page_names = [p["slug"] for p in new_pages]
    append_log(
        "ingest",
        source_filename,
        f"Source: {source_filename}\n"
        f"Pages created/updated: {', '.join(page_names)}\n"
        f"Summary: {analysis.get('summary', '')}",
    )

    print(f"\n=== Ingest complete! {len(new_pages)} pages created/updated. ===")


# ── Query ───────────────────────────────────────────────────────────────

def cmd_query(question):
    """Query the wiki."""
    print(f"\n--- Searching wiki...\n")

    index_content = read_index()
    if not index_content.strip() or "No sources ingested" in index_content:
        print("Wiki is empty. Ingest some sources first.")
        return

    # Step 1: Find relevant pages
    relevant = ollama_json([
        {
            "role": "system",
            "content": (
                "You help find relevant wiki pages. Return a JSON object with "
                'a key "pages" containing a list of page slugs (the kebab-case '
                "filenames without .md) that are relevant to the question. "
                "Only include pages that appear in the index."
            ),
        },
        {
            "role": "user",
            "content": f"Wiki index:\n{index_content}\n\nQuestion: {question}\n\nWhich pages are relevant?",
        },
    ])

    page_slugs = relevant.get("pages", [])
    if not page_slugs:
        print("No relevant pages found. Try rephrasing or ingest more sources.")
        return

    # Step 2: Read relevant pages
    print(f"  Reading: {', '.join(page_slugs)}")
    pages_content = []
    for slug in page_slugs:
        content = read_wiki_page(slug)
        if content:
            pages_content.append(f"--- {slug}.md ---\n{content}")

    if not pages_content:
        print("Could not read any of the identified pages.")
        return

    combined = "\n\n".join(pages_content)
    if len(combined) > 10000:
        combined = combined[:10000] + "\n\n[... truncated ...]"

    all_slugs = get_all_page_slugs()

    # Step 3: Synthesize answer
    print(f"\n--- Answer:\n")
    answer = ollama_chat([
        {
            "role": "system",
            "content": (
                "Answer questions using wiki pages as your knowledge base. "
                "Cite sources with (source: filename). "
                "Reference wiki pages with [[page-name]] in kebab-case. "
                "Be thorough but concise. Do not invent facts."
            ),
        },
        {
            "role": "user",
            "content": f"Wiki pages:\n{combined}\n\nQuestion: {question}",
        },
    ])

    # Normalize links in the answer
    answer = _normalize_wikilinks(answer, all_slugs)

    # Offer to save
    print(f"\nSave this answer to outputs/? (y/N)")
    save = input("> ").strip().lower()
    if save == "y":
        slug = slugify(question[:50])
        output_path = OUTPUTS_DIR / f"{slug}.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        content = (
            f"---\ntitle: {question}\ntype: query\ncreated: {today}\n---\n\n"
            f"# {question}\n\n{answer}\n"
        )
        output_path.write_text(content, encoding="utf-8")
        print(f"  saved: {output_path}")

        print(f"  File as a wiki map page too? (y/N)")
        if input("> ").strip().lower() == "y":
            write_page("maps", slug, content)
            update_index([{"slug": slug, "summary": question[:80], "section": "Maps"}])
            append_log("query>map", question[:50], "Filed query answer as map page.")
            print(f"  filed as map page!")


# ── Lint ────────────────────────────────────────────────────────────────

def cmd_lint():
    """Health-check the wiki."""
    print(f"\n--- Linting wiki...\n")

    # Collect all pages
    all_pages = {}
    for subdir in ("sources", "entities", "concepts", "maps"):
        dir_path = WIKI_DIR / subdir
        if dir_path.exists():
            for f in dir_path.glob("*.md"):
                content = f.read_text(encoding="utf-8")
                all_pages[f.stem] = {"path": f, "content": content, "subdir": subdir}

    if not all_pages:
        print("Wiki is empty. Nothing to lint.")
        return

    print(f"Found {len(all_pages)} wiki pages.\n")

    # Check for orphan pages (no inbound links)
    inbound_links = {name: set() for name in all_pages}
    for name, page in all_pages.items():
        links = re.findall(r"\[\[([^\]]+)\]\]", page["content"])
        for link in links:
            link_slug = slugify(link)
            if link_slug in inbound_links:
                inbound_links[link_slug].add(name)

    orphans = [name for name, links in inbound_links.items() if not links]
    if orphans:
        print(f"Orphan pages (no inbound links):")
        for o in orphans:
            print(f"  - [[{o}]]")
    else:
        print(f"No orphan pages.")

    # Find referenced but missing pages
    all_mentioned = set()
    for name, page in all_pages.items():
        links = re.findall(r"\[\[([^\]]+)\]\]", page["content"])
        for link in links:
            all_mentioned.add(slugify(link))

    missing = all_mentioned - set(all_pages.keys()) - {"index", "log", ""}
    if missing:
        print(f"\nReferenced but missing pages:")
        for m in sorted(missing):
            print(f"  - [[{m}]]")
    else:
        print(f"No missing page references.")

    # LLM analysis for contradictions and suggestions
    combined = ""
    for name, page in all_pages.items():
        snippet = page["content"][:500]
        combined += f"\n--- {name} ({page['subdir']}) ---\n{snippet}\n"

    if len(combined) > 10000:
        combined = combined[:10000]

    print(f"\nChecking for contradictions and suggestions...\n")
    ollama_chat([
        {
            "role": "system",
            "content": (
                "You are a wiki maintainer. Analyze these pages and report:\n"
                "1. Contradictions between pages\n"
                "2. Stale or outdated claims\n"
                "3. Missing cross-references\n"
                "4. Suggestions for new pages or topics\n"
                "Be concise and specific. Do not invent facts."
            ),
        },
        {"role": "user", "content": f"Wiki pages:\n{combined}"},
    ])

    append_log(
        "lint",
        "Wiki health check",
        f"Pages checked: {len(all_pages)}\n"
        f"Orphans: {len(orphans)}\n"
        f"Missing references: {len(missing)}",
    )

    print(f"\n=== Lint complete. ===")


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    global MODEL

    parser = argparse.ArgumentParser(
        description="BRAIN — Ollama-powered wiki maintenance agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python brain.py ingest raw/article.txt\n"
            "  python brain.py query \"What is spaced repetition?\"\n"
            "  python brain.py lint\n"
        ),
    )
    parser.add_argument(
        "command", choices=["ingest", "query", "lint"], help="Command to run"
    )
    parser.add_argument(
        "argument", nargs="?", default=None, help="File path (ingest) or question (query)"
    )
    parser.add_argument(
        "--model", default=None, help=f"Ollama model (default: {MODEL})"
    )

    args = parser.parse_args()

    if args.model:
        MODEL = args.model

    # Check Ollama is running
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    except requests.ConnectionError:
        print("Error: Ollama is not running. Start it with: ollama serve")
        sys.exit(1)

    if args.command == "ingest":
        if not args.argument:
            print("Usage: python brain.py ingest <file>")
            sys.exit(1)
        path = Path(args.argument)
        if not path.exists():
            print(f"Error: file not found: {path}")
            sys.exit(1)
        cmd_ingest(path)

    elif args.command == "query":
        if not args.argument:
            print('Usage: python brain.py query "your question"')
            sys.exit(1)
        cmd_query(args.argument)

    elif args.command == "lint":
        cmd_lint()


if __name__ == "__main__":
    main()
