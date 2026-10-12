#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["trafilatura>=2.0", "playwright==1.62.0"]
# ///
"""reach-render | local, free page -> markdown for `reach web`.

  reach-render.py render <url>   headless Chromium (JS), then extract
  reach-render.py extract <url>  read HTML on stdin (already fetched), then extract
  reach-render.py check          is the browser for the pinned Playwright installed? (exit 3 if not)
  reach-render.py install        download that browser (~110 MB into the Playwright cache)

Prints Jina-style output (Title / URL Source / Markdown Content) or nothing,
exiting non-zero with a one-line reason on stderr. playwright is pinned to the
version whose browsers live in ~/.cache/ms-playwright; bump both together.
"""
import sys


def extract(html: str, url: str) -> str:
    import trafilatura

    md = trafilatura.extract(
        html, url=url, output_format="markdown", include_links=True,
        include_tables=True, include_images=False, favor_recall=True,
    ) or ""
    meta = trafilatura.extract_metadata(html, default_url=url)
    title = (meta.title if meta and meta.title else "").strip()
    return f"Title: {title}\n\nURL Source: {url}\n\nMarkdown Content:\n{md.strip()}\n" if md.strip() else ""


def render(url: str) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        try:
            page = browser.new_page(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/141.0 Safari/537.36",
                locale="en-US",
            )
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:  # let SPAs hydrate, but never hang on chatty pages
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            if resp is not None and resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}")
            html, final = page.content(), page.url
            md = extract(html, final)
            if not md:  # extractor found no article body: fall back to visible text
                text = page.inner_text("body").strip()
                if text:
                    md = f"Title: {page.title()}\n\nURL Source: {final}\n\nMarkdown Content:\n{text}\n"
            return md
        finally:
            browser.close()


MISSING = 3  # exit code the reach wrapper turns into an install prompt


def browser_missing(e: Exception) -> bool:
    return "Executable doesn't exist" in str(e) or "playwright install" in str(e)


def check() -> int:
    from importlib.metadata import version
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception as e:
        if browser_missing(e):
            print(f"headless Chromium for Playwright {version('playwright')} is not installed", file=sys.stderr)
            return MISSING
        print(f"{type(e).__name__}: {str(e).splitlines()[0]}", file=sys.stderr)
        return 1
    print(f"ok: Playwright {version('playwright')} + headless Chromium")
    return 0


def install() -> int:
    import subprocess

    # Runs this env's own Playwright, so the browser build always matches the pin.
    return subprocess.call([sys.executable, "-m", "playwright", "install", "chromium-headless-shell"])


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in ("check", "install"):
        return check() if sys.argv[1] == "check" else install()
    if len(sys.argv) != 3 or sys.argv[1] not in ("render", "extract"):
        print(__doc__, file=sys.stderr)
        return 2
    mode, url = sys.argv[1], sys.argv[2]
    try:
        out = render(url) if mode == "render" else extract(sys.stdin.read(), url)
    except Exception as e:  # one line, the caller logs it as the reason
        if browser_missing(e):
            print("headless Chromium not installed (run: reach setup)", file=sys.stderr)
            return MISSING
        print(f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}", file=sys.stderr)
        return 1
    if not out:
        print("no readable content", file=sys.stderr)
        return 1
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
