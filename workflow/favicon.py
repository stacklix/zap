"""Fetch site favicon using HTML <link> discovery and /favicon.ico fallback (browser-like)."""

from __future__ import annotations

import re
import ssl
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener, getproxies, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
MAX_HTML_BYTES = 768_000
MAX_IMAGE_BYTES = 2_048_000
FETCH_TIMEOUT = 12


def _request(url: str) -> Request:
    return Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            # Browser-like default headers improve compatibility on stricter sites/CDNs.
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
        method="GET",
    )


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _open_url(req: Request, timeout: int, context: ssl.SSLContext):
    """Open request with system/environment proxy support when available."""
    proxies = getproxies() or {}
    if proxies:
        opener = build_opener(ProxyHandler(proxies), HTTPSHandler(context=context))
        return opener.open(req, timeout=timeout)
    return urlopen(req, timeout=timeout, context=context)


def _format_fetch_error(url: str, exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code} for {url}"
    if isinstance(exc, URLError):
        return f"URL error for {url}: {exc.reason}"
    if isinstance(exc, TimeoutError):
        return f"Timeout fetching {url}"
    if isinstance(exc, OSError):
        return f"OS error for {url}: {exc}"
    return f"Fetch error for {url}: {exc}"


def _content_type(headers) -> str:
    if not headers:
        return ""
    try:
        raw = headers.get_content_type() or ""
    except Exception:
        raw = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
    return raw.split(";")[0].strip().lower()


def fetch_limited(url: str, limit: int) -> Optional[Tuple[str, str, bytes]]:
    """GET url; return (final_url, content_type, body) or None. Follows redirects."""
    out, _err = fetch_limited_with_error(url, limit)
    return out


def fetch_limited_with_error(url: str, limit: int) -> tuple[Optional[Tuple[str, str, bytes]], Optional[str]]:
    """GET url; return ((final_url, content_type, body) or None, error string)."""
    try:
        with _open_url(_request(url), timeout=FETCH_TIMEOUT, context=_ssl_context()) as resp:
            final = resp.geturl()
            ct = _content_type(resp.headers)
            chunk = resp.read(limit + 1)
        if len(chunk) > limit:
            return None, f"Response exceeds limit ({limit} bytes): {url}"
        return (final, ct, chunk), None
    except (HTTPError, URLError, OSError, ValueError, TimeoutError) as e:
        return None, _format_fetch_error(url, e)


def _ext_from_type(ct: str, url: str) -> str:
    if "svg" in ct:
        return ".svg"
    if "png" in ct:
        return ".png"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "webp" in ct:
        return ".webp"
    if "icon" in ct or ct == "image/x-icon":
        return ".ico"
    path = urlparse(url).path.lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".ico", ".svg"):
        if path.endswith(ext):
            return ext if ext != ".jpeg" else ".jpg"
    return ".ico"


def _looks_like_image(data: bytes, ext: str) -> bool:
    if not data or len(data) < 4:
        return False
    if ext == ".svg" or data.strip()[:1] == b"<":
        head = data[:4000].lower()
        return b"<svg" in head or head.strip().startswith(b"<?xml")
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if data[:3] == b"GIF":
        return True
    if data[:2] == b"\xff\xd8":
        return True
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return True
    if data[:4] in (b"\x00\x00\x01\x00", b"\x00\x00\x02\x00"):
        return True
    return False


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "link":
            return
        d = {k.lower(): (v or "") for k, v in attrs}
        href = d.get("href", "").strip()
        if not href:
            return
        rel = d.get("rel", "").strip().lower()
        sizes = d.get("sizes", "").strip().lower()
        self.links.append((rel, href, sizes))


def _parse_sizes_max(sizes: str) -> int:
    best = 0
    for part in sizes.split():
        m = re.match(r"^(\d+)x(\d+)$", part.strip())
        if m:
            best = max(best, int(m.group(1)), int(m.group(2)))
    return best


def _rel_tokens(rel: str) -> List[str]:
    return [t for t in rel.split() if t]


def _candidate_score(rel: str, sizes: str) -> Optional[Tuple[int, int]]:
    tokens = set(_rel_tokens(rel))
    if not tokens & {"icon", "shortcut", "apple-touch-icon", "apple-touch-icon-precomposed"}:
        return None
    if "mask-icon" in tokens:
        return None

    max_dim = _parse_sizes_max(sizes)
    is_apple = "apple-touch-icon" in tokens or "apple-touch-icon-precomposed" in tokens
    is_shortcut = "shortcut" in tokens and "icon" in tokens
    is_plain_icon = "icon" in tokens and not is_apple

    if is_plain_icon:
        return (400, max_dim)
    if is_apple:
        return (300, max_dim)
    if is_shortcut or "icon" in tokens:
        return (200, max_dim)
    return None


def _sorted_hrefs(links: List[Tuple[str, str, str]], base_url: str) -> List[str]:
    scored: List[Tuple[Tuple[int, int], str]] = []
    for rel, href, sizes in links:
        sc = _candidate_score(rel, sizes)
        if sc is None:
            continue
        tier, dim = sc
        abs_url = urljoin(base_url, href)
        scored.append(((tier, min(dim, 512)), abs_url))
    scored.sort(key=lambda x: (x[0][0], x[0][1]), reverse=True)
    out: List[str] = []
    seen = set()
    for _, u in scored:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _fetch_favicon_once(page_url: str) -> tuple[Optional[Tuple[bytes, str]], Optional[str]]:
    """Download favicon bytes once for page_url and return (result, error)."""
    page, page_err = fetch_limited_with_error(page_url, MAX_HTML_BYTES)
    if not page:
        return None, page_err or f"Page fetch failed: {page_url}"
    final_page_url, ct, body = page

    if ct.startswith("image/"):
        ext = _ext_from_type(ct, final_page_url)
        if _looks_like_image(body, ext):
            return (body, ext), None

    try:
        text = body.decode("utf-8", errors="replace")
    except Exception:
        text = ""

    parser = _LinkParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        pass

    for href in _sorted_hrefs(parser.links, final_page_url):
        img, _img_err = fetch_limited_with_error(href, MAX_IMAGE_BYTES)
        if not img:
            continue
        _, ict, raw = img
        ext = _ext_from_type(ict, href)
        if _looks_like_image(raw, ext):
            return (raw, ext), None

    parsed = urlparse(final_page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    ico_url = urljoin(origin + "/", "favicon.ico")
    img, ico_err = fetch_limited_with_error(ico_url, MAX_IMAGE_BYTES)
    if img:
        _, _, raw = img
        ext = ".ico"
        if _looks_like_image(raw, ext):
            return (raw, ext), None

    return None, f"No valid favicon found at {final_page_url}; favicon.ico result: {ico_err or 'not image/empty'}"


def _url_without_leading_www(page_url: str) -> Optional[str]:
    parsed = urlparse(page_url)
    host = parsed.hostname or ""
    if not host.lower().startswith("www."):
        return None
    bare_host = host[4:]
    if not bare_host:
        return None
    netloc = bare_host
    if parsed.port is not None:
        netloc = f"{bare_host}:{parsed.port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def fetch_favicon(page_url: str) -> Optional[Tuple[bytes, str]]:
    """
    Download favicon bytes for page_url.
    Returns (data, extension_with_dot) or None.
    If first pass fails and host starts with www., retry once without www.
    """
    got, _err = _fetch_favicon_once(page_url)
    if got is not None:
        return got
    fallback_url = _url_without_leading_www(page_url)
    if fallback_url and fallback_url != page_url:
        got2, _err2 = _fetch_favicon_once(fallback_url)
        return got2
    return None


def fetch_favicon_with_error(page_url: str) -> tuple[Optional[Tuple[bytes, str]], Optional[str]]:
    """Like fetch_favicon but returns backend-friendly failure reason."""
    got, err = _fetch_favicon_once(page_url)
    if got is not None:
        return got, None
    fallback_url = _url_without_leading_www(page_url)
    if fallback_url and fallback_url != page_url:
        got2, err2 = _fetch_favicon_once(fallback_url)
        if got2 is not None:
            return got2, None
        return None, f"{err}; fallback without www failed: {err2}"
    return None, err
