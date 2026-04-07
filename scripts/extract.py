#!/usr/bin/env python3
"""
Extract text from PDF, HTML files, and web URLs.
Saves extracted text as .extracted.md alongside the original in raw/.

Usage:
    python scripts/extract.py raw/document.pdf
    python scripts/extract.py raw/page.html
    python scripts/extract.py https://example.com/article

Dependencies:
    pip install pdfplumber beautifulsoup4 requests
"""

import sys
import os
from pathlib import Path


def extract_pdf(filepath: Path) -> str:
    """Extract text from a PDF file using pdfplumber."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"## Page {i}\n\n{page_text}")
    return "\n\n".join(text_parts)


def extract_html_file(filepath: Path) -> str:
    """Extract text from a local HTML file."""
    from bs4 import BeautifulSoup

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()
    return _extract_html(html)


def extract_url(url: str) -> str:
    """Fetch and extract text from a web URL."""
    import requests
    from bs4 import BeautifulSoup

    headers = {"User-Agent": "Mozilla/5.0 (compatible; BrainExtractor/1.0)"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return _extract_html(response.text, url=url)


def _extract_html(html: str, url: str = None) -> str:
    """Parse HTML and extract readable text."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav, footer elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled"

    # Try to find the main content area
    main = soup.find("main") or soup.find("article") or soup.find("body")
    if main is None:
        main = soup

    text = main.get_text(separator="\n", strip=True)

    # Clean up excessive blank lines
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)

    header = f"# {title}\n"
    if url:
        header += f"\nSource URL: {url}\n"
    return header + "\n" + text


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract.py <file_or_url>")
        print("Supported: .pdf, .html, web URLs")
        sys.exit(1)

    source = sys.argv[1]

    # Determine if it's a URL or file
    if source.startswith("http://") or source.startswith("https://"):
        print(f"Fetching URL: {source}")
        text = extract_url(source)
        # Save in raw/ with a sanitized filename
        from urllib.parse import urlparse
        parsed = urlparse(source)
        slug = parsed.netloc + parsed.path
        slug = slug.strip("/").replace("/", "-").replace(".", "-")
        output_path = Path("raw") / f"{slug}.extracted.md"
    else:
        filepath = Path(source)
        if not filepath.exists():
            print(f"Error: file not found: {filepath}")
            sys.exit(1)

        ext = filepath.suffix.lower()
        if ext == ".pdf":
            print(f"Extracting PDF: {filepath}")
            text = extract_pdf(filepath)
        elif ext in (".html", ".htm"):
            print(f"Extracting HTML: {filepath}")
            text = extract_html_file(filepath)
        else:
            print(f"Error: unsupported format '{ext}'. Supported: .pdf, .html")
            sys.exit(1)

        output_path = filepath.with_suffix(filepath.suffix + ".extracted.md")

    # Write extracted text
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Saved to: {output_path}")
    print(f"Length: {len(text)} characters")


if __name__ == "__main__":
    main()
