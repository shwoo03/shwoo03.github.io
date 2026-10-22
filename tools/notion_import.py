#!/usr/bin/env python3
"""Import a Notion page as a Chirpy post, keeping its look as close to Notion as possible.

Usage:
  NOTION_TOKEN=ntn_xxx python3 tools/notion_import.py <notion-url-or-page-id> [options]

By default the post is written to _posts/ and every image/file is downloaded
(original bytes) to assets/img/notion/<page-id>/. Re-running with the same page
updates the existing post in place. See --help for options.

Styles for the generated markup live in _sass/notion.scss.
Only the Python standard library is used.
"""

import argparse
import datetime as dt
import html
import json
import mimetypes
import os
import re
import shutil
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent

LIST_TYPES = ("bulleted_list_item", "numbered_list_item", "to_do")
HEADING_LEVELS = {"heading_1": 2, "heading_2": 3, "heading_3": 4, "heading_4": 5}

# Notion code-block language names -> Rouge lexer names
CODE_LANGS = {
    "plain text": "plaintext",
    "c++": "cpp",
    "c#": "csharp",
    "f#": "fsharp",
    "objective-c": "objective_c",
    "visual basic": "vb",
    "vb.net": "vbnet",
    "java/c/c++/c#": "java",
    "makefile": "make",
    "assembly": "nasm",
    "webassembly": "wasm",
    "flow": "javascript",
    "docker": "docker",
    "shell": "shell",
    "markup": "html",
    "ocaml": "ocaml",
    "reason": "reasonml",
}

# Front-matter fields that may come from Notion database properties
PROPERTY_ALIASES = {
    "tags": ("tags", "tag", "태그"),
    "categories": ("categories", "category", "카테고리", "분류"),
    "date": ("date", "날짜", "작성일", "발행일", "published"),
    "description": ("description", "설명", "요약", "summary"),
    "slug": ("slug", "슬러그"),
}


def log(msg):
    print(msg, file=sys.stderr)


# --------------------------------------------------------------------------- #
# HTTP / Notion API
# --------------------------------------------------------------------------- #


class NotionError(Exception):
    def __init__(self, status, message):
        hints = {
            401: "토큰이 잘못됐습니다. NOTION_TOKEN 값을 확인하세요.",
            403: "Integration에 읽기 권한(Read content)이 없습니다.",
            404: "페이지를 찾을 수 없습니다. 페이지의 ··· → 연결(Connections)에 Integration을 추가했는지 확인하세요.",
        }
        super().__init__(f"Notion API {status}: {message}" + (f"\n→ {hints[status]}" if status in hints else ""))
        self.status = status


def http_get(url, timeout=30, limit=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(limit) if limit else resp.read()
        return data, resp.headers, resp.geturl()


class NotionClient:
    def __init__(self, token, record=None):
        self.token = token
        self.record = record  # dict that collects responses for --record

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(6):
            req = urllib.request.Request(
                NOTION_API + path,
                data=data,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Notion-Version": NOTION_VERSION,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.load(resp)
                if self.record is not None:
                    self.record[request_key(method, path, body)] = result
                return result
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    time.sleep(min(float(e.headers.get("Retry-After") or 2**attempt), 30))
                    continue
                try:
                    message = json.loads(e.read()).get("message", "")
                except ValueError:
                    message = e.reason
                raise NotionError(e.code, message) from None
            except urllib.error.URLError:
                time.sleep(2**attempt)
        raise NotionError(0, f"{method} {path}: 재시도 한도를 넘었습니다.")


class ReplayClient:
    """Serves responses saved with --record (offline testing)."""

    def __init__(self, path):
        self.responses = json.loads(Path(path).read_text(encoding="utf-8"))

    def call(self, method, path, body=None):
        key = request_key(method, path, body)
        if key not in self.responses:
            raise NotionError(404, f"녹화본에 없는 요청: {key}")
        return self.responses[key]


def request_key(method, path, body):
    return f"{method} {path} {json.dumps(body, sort_keys=True) if body is not None else ''}".strip()


def paginate(client, method, path, body=None):
    results, cursor = [], None
    while True:
        if method == "GET":
            sep = "&" if "?" in path else "?"
            full = f"{path}{sep}page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
            res = client.call("GET", full)
        else:
            res = client.call("POST", path, {**(body or {}), "page_size": 100, **({"start_cursor": cursor} if cursor else {})})
        results.extend(res.get("results", []))
        if not res.get("has_more"):
            return results
        cursor = res.get("next_cursor")


def fetch_tree(client, block_id, counter):
    blocks = paginate(client, "GET", f"/blocks/{block_id}/children")
    counter[0] += len(blocks)
    print(f"\r  블록 {counter[0]}개 읽음", end="", file=sys.stderr)
    for b in blocks:
        t = b["type"]
        if t in ("child_page", "child_database"):
            continue
        if t == "synced_block" and (b["synced_block"].get("synced_from") or {}).get("block_id"):
            try:
                b["_children"] = fetch_tree(client, b["synced_block"]["synced_from"]["block_id"], counter)
                continue
            except NotionError:
                pass  # original not shared with the integration; fall back to the copy
        if b.get("has_children"):
            b["_children"] = fetch_tree(client, b["id"], counter)
    return blocks


def parse_page_id(value):
    parsed = urllib.parse.urlparse(value.strip())
    query = urllib.parse.parse_qs(parsed.query)
    candidate = query["p"][0] if "p" in query else (parsed.path.rstrip("/").split("/")[-1] if parsed.scheme else value.strip())
    m = re.search(r"[0-9a-fA-F]{32}$", candidate.replace("-", ""))
    if not m:
        raise SystemExit(f"노션 페이지 ID를 찾을 수 없습니다: {value}")
    h = m.group(0).lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def notion_url(page_id):
    return f"https://www.notion.so/{page_id.replace('-', '')}"


# --------------------------------------------------------------------------- #
# Assets
# --------------------------------------------------------------------------- #


class Assets:
    """Downloads files into a staging directory and hands back their public URL."""

    def __init__(self, stage_dir, url_prefix):
        self.dir = Path(stage_dir)
        self.prefix = url_prefix
        self.cache = {}
        self.used = set()
        self.warnings = []

    def fetch(self, url, name_hint=None, quiet=False):
        if not url:
            return None
        if url in self.cache:
            return self.cache[url]
        try:
            data, headers, final_url = http_get(url, timeout=60)
        except Exception as e:  # noqa: BLE001 - any failure falls back to the remote URL
            if not quiet:
                self.warnings.append(f"다운로드 실패 ({e}): {url[:120]}")
            self.cache[url] = None
            return None
        name = self._unique(self._name(name_hint, final_url, headers.get("Content-Type")))
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / name
        path.write_bytes(data)
        asset = {"url": self.prefix + urllib.parse.quote(name), "path": path, "name": name, "size": len(data)}
        self.cache[url] = asset
        return asset

    def _name(self, hint, url, content_type):
        raw = hint or urllib.parse.unquote(urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]) or "file"
        stem, ext = os.path.splitext(raw)
        if not re.fullmatch(r"\.[A-Za-z0-9]{1,5}", ext or ""):
            stem = raw
            ctype = (content_type or "").split(";")[0].strip()
            ext = {"image/jpeg": ".jpg"}.get(ctype) or mimetypes.guess_extension(ctype) or ""
        stem = re.sub(r"[^\w.\-]+", "-", stem, flags=re.UNICODE).strip("-.") or "file"
        return stem[:80] + ext.lower()

    def _unique(self, name):
        stem, ext = os.path.splitext(name)
        candidate, n = name, 2
        while candidate.lower() in self.used:
            candidate = f"{stem}-{n}{ext}"
            n += 1
        self.used.add(candidate.lower())
        return candidate


def image_size(path):
    """Return (width, height) for PNG/JPEG/GIF/WebP files, else None."""
    try:
        with open(path, "rb") as f:
            head = f.read(64 * 1024)
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
        return struct.unpack(">II", head[16:24])
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", head[6:10])
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        chunk = head[12:16]
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", head[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if chunk == b"VP8L":
            b = head[21:25]
            return 1 + (((b[1] & 0x3F) << 8) | b[0]), 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
        if chunk == b"VP8X":
            return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
    if head[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5 : i + 9])
                return w, h
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", head[i + 2 : i + 4])[0]
    return None


# --------------------------------------------------------------------------- #
# Web metadata (bookmark cards, embed checks)
# --------------------------------------------------------------------------- #


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.icons, self.title, self._in_title = {}, [], "", False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"])
        elif tag == "link" and "icon" in a.get("rel", "").lower() and a.get("href"):
            self.icons.append(a["href"])
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def fetch_page_meta(url):
    data, headers, final_url = http_get(url, timeout=15, limit=768 * 1024)
    m = re.search(r"charset=([\w-]+)", headers.get("Content-Type", "")) or re.search(
        r"<meta[^>]+charset=[\"']?([\w-]+)", data[:4096].decode("ascii", "replace"), re.I
    )
    try:
        text = data.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError:
        text = data.decode("utf-8", errors="replace")
    parser = _MetaParser()
    try:
        parser.feed(text)
    except Exception:  # noqa: BLE001 - malformed HTML still yields partial metadata
        pass
    m = parser.meta
    icon = parser.icons[0] if parser.icons else "/favicon.ico"
    image = m.get("og:image") or m.get("twitter:image")
    return {
        "title": (m.get("og:title") or m.get("twitter:title") or parser.title).strip(),
        "description": (m.get("og:description") or m.get("twitter:description") or m.get("description") or "").strip(),
        "image": urllib.parse.urljoin(final_url, image) if image else None,
        "icon": urllib.parse.urljoin(final_url, icon),
        "headers": headers,
    }


def frame_blocked(headers):
    xfo = (headers.get("X-Frame-Options") or "").lower()
    if "deny" in xfo or "sameorigin" in xfo:
        return True
    csp = headers.get("Content-Security-Policy") or ""
    m = re.search(r"frame-ancestors([^;]*)", csp, re.I)
    return bool(m and "*" not in m.group(1).split())


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #


def esc(text):
    return html.escape(text, quote=True)


def md_escape(text):
    """Escape kramdown syntax in plain text (run before HTML-escaping)."""
    text = re.sub(r"([\\`*_\[\]{}|$~#])", r"\\\1", text)
    text = re.sub(r"-(?=-)", r"\\-", text)  # no en/em-dash conversion
    return re.sub(r"\.(?=\.\.)", r"\\.", text)  # no ellipsis conversion


def escape_line_start(text):
    m = re.match(r"[ \t]+", text)
    if m:
        text = "&nbsp;" * len(m.group(0)) + text[m.end():]
    text = re.sub(r"^([+\-:=])", r"\\\1", text)
    return re.sub(r"^(\d+)\.", r"\1\\.", text)


def indent(text, prefix):
    return "\n".join(prefix + line if line.strip() else "" for line in text.split("\n"))


def md_div(classes, inner, tag="div", attrs="", head=""):
    head = f"{head}\n" if head else ""
    return f'<{tag} class="{classes}"{attrs} markdown="1">\n{head}\n{inner}\n\n</{tag}>'


def color_class(color):
    if not color or color == "default":
        return ""
    if color.endswith("_background"):
        return f"notion-bg-{color[:-11]}"
    return f"notion-c-{color}"


def plain(rich_text):
    return "".join(r.get("plain_text", "") for r in rich_text or [])


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def fix_href(href):
    if href.startswith("/"):
        return "https://www.notion.so" + href
    return href


def file_url(obj):
    if not obj:
        return None
    kind = obj.get("type")
    return (obj.get(kind) or {}).get("url") if kind in ("file", "external", "file_upload") else None


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def format_date(value):
    if not value:
        return ""
    d = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo:
        d = d.astimezone(KST)
    out = f"{d.year}년 {d.month}월 {d.day}일"
    return out + (f" {d.hour:02d}:{d.minute:02d}" if "T" in value else "")


# --------------------------------------------------------------------------- #
# Converter
# --------------------------------------------------------------------------- #


class Converter:
    def __init__(self, client, assets, web=True):
        self.client = client
        self.assets = assets
        self.web = web
        self.uses_math = False
        self.uses_mermaid = False
        self.heading_ids = {}
        self.headings = []
        self.page_cache = {}
        self.user_cache = {}
        self.warnings = []

    # ---- rich text -------------------------------------------------------- #

    def rich_text(self, items, md=True):
        out = []
        for r in items or []:
            a = r.get("annotations") or {}
            if r.get("type") == "equation":
                expr = r["equation"]["expression"]
                self.uses_math = True
                s = f"$${expr}$$" if md else f"\\({esc(expr)}\\)"
            elif a.get("code"):
                s = f"<code>{esc(r.get('plain_text', ''))}</code>"
            else:
                s = r.get("plain_text", "")
                s = esc(md_escape(s) if md else s).replace("\n", "<br>")
            if a.get("bold"):
                s = f"<strong>{s}</strong>"
            if a.get("italic"):
                s = f"<em>{s}</em>"
            if a.get("strikethrough"):
                s = f"<del>{s}</del>"
            if a.get("underline"):
                s = f'<span class="notion-underline">{s}</span>'
            cls = color_class(a.get("color"))
            if cls:
                s = f'<span class="{cls}">{s}</span>'
            if r.get("href"):
                s = f'<a href="{esc(fix_href(r["href"]))}">{s}</a>'
            out.append(s)
        return "".join(out)

    def block_text(self, items):
        return escape_line_start(self.rich_text(items))

    def caption(self, items):
        return f'<div class="notion-caption">{self.rich_text(items, md=False)}</div>' if plain(items) else ""

    # ---- headings --------------------------------------------------------- #

    def collect_headings(self, blocks, used=None):
        used = set() if used is None else used
        for b in blocks:
            if b["type"] in HEADING_LEVELS:
                base = slugify(plain(b[b["type"]]["rich_text"])) or "section"
                hid, n = base, 1
                while hid in used:
                    hid = f"{base}-{n}"
                    n += 1
                used.add(hid)
                self.heading_ids[b["id"]] = hid
                self.headings.append((HEADING_LEVELS[b["type"]], hid, self.rich_text(b[b["type"]]["rich_text"], md=False)))
            if b.get("_children"):
                self.collect_headings(b["_children"], used)

    # ---- blocks ----------------------------------------------------------- #

    def render_blocks(self, blocks):
        parts, i = [], 0
        while i < len(blocks):
            t = blocks[i]["type"]
            if t in LIST_TYPES:
                j = i
                while j < len(blocks) and blocks[j]["type"] == t:
                    j += 1
                parts.append(self.render_list(t, blocks[i:j]))
                i = j
                continue
            rendered = self.render_block(blocks[i])
            if rendered:
                parts.append(rendered)
            i += 1
        return "\n\n".join(parts)

    def children(self, b):
        return self.render_blocks(b.get("_children") or [])

    def render_block(self, b):
        t = b["type"]
        handler = getattr(self, f"b_{t}", None)
        if handler is None:
            self.warnings.append(f"지원하지 않는 블록: {t}")
            return f"<!-- notion: unsupported block '{t}' -->"
        return handler(b, b[t])

    def render_list(self, t, items):
        marker = {"bulleted_list_item": "- ", "numbered_list_item": "1. ", "to_do": "- "}[t]
        pad = " " * len(marker)
        lines, loose = [], False
        for b in items:
            d = b[t]
            text = self.block_text(d["rich_text"]) or "&nbsp;"
            cls = color_class(d.get("color"))
            if cls:
                text = f'<span class="{cls}">{text}</span>'
            if t == "to_do":
                text = ("[x] " if d.get("checked") else "[ ] ") + f'<span class="notion-todo-text">{text}</span>'
            item = marker + text
            kids = b.get("_children")
            if kids:
                nested_list_first = kids[0]["type"] in LIST_TYPES
                loose = loose or not nested_list_first
                item += ("\n" if nested_list_first else "\n\n") + indent(self.render_blocks(kids), pad)
            lines.append(item)
        attrs = [f".notion-{t.replace('_', '-')}"]
        first = items[0][t]
        if t == "numbered_list_item":
            if first.get("list_start_index"):
                attrs.append(f'start="{int(first["list_start_index"])}"')
            style = {"letters": "lower-alpha", "roman": "lower-roman"}.get(first.get("list_format_style"))
            if style:
                attrs.append(f'style="list-style-type: {style}"')
        return ("\n\n" if loose else "\n").join(lines) + "\n{: " + " ".join(attrs) + "}"

    def with_children(self, head, b):
        kids = self.children(b)
        return head + ("\n\n" + md_div("notion-indent", kids) if kids else "")

    def b_paragraph(self, b, d):
        text = self.block_text(d["rich_text"])
        if not text:
            head = '<div class="notion-blank"></div>'
        else:
            cls = color_class(d.get("color"))
            head = text + (f"\n{{: .{cls}}}" if cls else "")
        return self.with_children(head, b)

    def _heading(self, b, d):
        level = HEADING_LEVELS[b["type"]]
        hid = self.heading_ids.get(b["id"], "")
        cls = color_class(d.get("color"))
        if d.get("is_toggleable"):
            cls_attr = f' class="{cls}"' if cls else ""
            h = f'<h{level} id="{esc(hid)}"{cls_attr}>{self.rich_text(d["rich_text"], md=False)}</h{level}>'
            return md_div("notion-toggle notion-toggle-heading", self.children(b), tag="details", head=f"<summary>{h}</summary>")
        ial = f'{{: id="{esc(hid)}"' + (f" .{cls}" if cls else "") + "}"
        return f"{'#' * level} {self.rich_text(d['rich_text'])}\n{ial}"

    b_heading_1 = b_heading_2 = b_heading_3 = b_heading_4 = _heading

    def b_quote(self, b, d):
        body = self.block_text(d["rich_text"])
        kids = self.children(b)
        if kids:
            body += "\n\n" + kids
        quoted = "\n".join("> " + line if line else ">" for line in body.split("\n"))
        cls = color_class(d.get("color"))
        return md_div(cls, quoted) if cls else quoted

    def b_callout(self, b, d):
        icon = self.icon_html(d.get("icon"))
        content = self.block_text(d["rich_text"])
        kids = self.children(b)
        if kids:
            content = f"{content}\n\n{kids}" if content else kids
        color = d.get("color") or "default"
        cls = "notion-callout " + (color_class(color) or "notion-callout-plain")
        if not color.endswith("_background") and color != "default":
            cls += " notion-callout-plain"
        icon_div = f'<div class="notion-callout-icon">{icon}</div>' if icon else ""
        return md_div(cls, md_div("notion-callout-content", content), head=icon_div)

    def b_toggle(self, b, d):
        cls = color_class(d.get("color"))
        summary = f"<summary>{self.rich_text(d['rich_text'], md=False)}</summary>"
        return md_div(f"notion-toggle {cls}".strip(), self.children(b), tag="details", head=summary)

    def b_code(self, b, d):
        lang = (d.get("language") or "plain text").lower()
        if lang == "mermaid":
            self.uses_mermaid = True
        lang = CODE_LANGS.get(lang, lang.replace(" ", "_"))
        code = plain(d["rich_text"])
        fence = "```"
        while fence in code:
            fence += "`"
        out = f"{fence}{lang}\n{code}\n{fence}"
        cap = self.caption(d.get("caption"))
        return out + (f"\n\n{cap}" if cap else "")

    def b_equation(self, b, d):
        self.uses_math = True
        return f"$$\n{d['expression']}\n$$"

    def b_divider(self, b, d):
        return "---"

    def b_image(self, b, d):
        src = file_url(d)
        asset = self.assets.fetch(src)
        url = asset["url"] if asset else src
        alt = plain(d.get("caption")) or (os.path.splitext(asset["name"])[0] if asset else "image")
        out = f"![{esc(md_escape(alt))}]({url})"
        size = image_size(asset["path"]) if asset else None
        if size:
            out += f'{{: w="{size[0]}" h="{size[1]}" }}'
        if plain(d.get("caption")):
            out += f"\n<em>{self.rich_text(d['caption'])}</em>"
        return out

    def b_video(self, b, d):
        src = file_url(d)
        frame = self.video_iframe(src) if d.get("type") == "external" else None
        if frame:
            body = frame
        elif d.get("type") == "external" and not re.search(r"\.(mp4|webm|ogg|mov|m4v)(\?|$)", src or "", re.I):
            return self.b_embed(b, {"url": src, "caption": d.get("caption")})
        else:
            asset = self.assets.fetch(src)
            url = asset["url"] if asset else src
            body = f'<video class="embed-video file" controls preload="metadata"><source src="{esc(url)}"></video>'
        cap = self.caption(d.get("caption"))
        return f'<div class="notion-media">{body}{cap}</div>'

    def b_audio(self, b, d):
        asset = self.assets.fetch(file_url(d))
        url = asset["url"] if asset else file_url(d)
        cap = self.caption(d.get("caption"))
        return f'<div class="notion-media"><audio class="embed-audio file" controls src="{esc(url)}"></audio>{cap}</div>'

    def b_pdf(self, b, d):
        asset = self.assets.fetch(file_url(d))
        url = asset["url"] if asset else file_url(d)
        name = asset["name"] if asset else url.split("?")[0].rsplit("/", 1)[-1]
        cap = self.caption(d.get("caption"))
        return (
            f'<div class="notion-media"><iframe class="notion-pdf" src="{esc(url)}" title="{esc(name)}"></iframe>'
            f"{self.file_row(url, name, asset)}{cap}</div>"
        )

    def b_file(self, b, d):
        src = file_url(d)
        asset = self.assets.fetch(src, name_hint=d.get("name"))
        url = asset["url"] if asset else src
        name = d.get("name") or (asset["name"] if asset else "file")
        return f'<div class="notion-media">{self.file_row(url, name, asset)}{self.caption(d.get("caption"))}</div>'

    def file_row(self, url, name, asset):
        size = f'<span class="notion-file-size">{human_size(asset["size"])}</span>' if asset else ""
        return f'<a class="notion-file" href="{esc(url)}" download><span class="notion-file-icon"></span><span class="notion-file-name">{esc(name)}</span>{size}</a>'

    def b_bookmark(self, b, d):
        return self.bookmark_card(d.get("url", ""), d.get("caption"))

    def b_link_preview(self, b, d):
        return self.bookmark_card(d.get("url", ""))

    def b_embed(self, b, d):
        url = d.get("url", "")
        frame = self.video_iframe(url) or self.provider_embed(url)
        if frame is None and self.web:
            try:
                headers = http_get(url, timeout=15, limit=64 * 1024)[1]
                if not frame_blocked(headers):
                    frame = f'<iframe class="notion-embed-frame" src="{esc(url)}" loading="lazy" allowfullscreen></iframe>'
            except Exception:  # noqa: BLE001 - unreachable embeds become bookmark cards
                pass
        if frame is None:
            return self.bookmark_card(url, d.get("caption"))
        return f'<div class="notion-embed">{frame}{self.caption(d.get("caption"))}</div>'

    def video_iframe(self, url):
        url = url or ""
        m = re.search(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)([\w-]{11})", url)
        if m:
            src = f"https://www.youtube.com/embed/{m.group(1)}"
        else:
            m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url)
            if m:
                src = f"https://player.vimeo.com/video/{m.group(1)}"
            else:
                m = re.search(r"loom\.com/share/(\w+)", url)
                if not m:
                    return None
                src = f"https://www.loom.com/embed/{m.group(1)}"
        return (
            f'<iframe class="embed-video" loading="lazy" src="{src}" title="video player" frameborder="0" referrerpolicy="strict-origin-when-cross-origin" '
            'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'
        )

    def provider_embed(self, url):
        host = urllib.parse.urlparse(url).netloc.lower()
        if "figma.com" in host:
            src = "https://www.figma.com/embed?embed_host=share&url=" + urllib.parse.quote(url, safe="")
            return f'<iframe class="notion-embed-frame" src="{esc(src)}" loading="lazy" allowfullscreen></iframe>'
        if "codepen.io" in host and "/pen/" in url:
            return f'<iframe class="notion-embed-frame" src="{esc(url.replace("/pen/", "/embed/"))}" loading="lazy"></iframe>'
        if "open.spotify.com" in host:
            src = url.replace("open.spotify.com/", "open.spotify.com/embed/")
            return f'<iframe class="notion-embed-frame notion-embed-spotify" src="{esc(src)}" loading="lazy" allow="encrypted-media"></iframe>'
        if host == "gist.github.com":
            return f'<script src="{esc(url.split("?")[0].rstrip("/"))}.js"></script>'
        if host in ("twitter.com", "x.com", "www.twitter.com", "www.x.com"):
            tweet = re.sub(r"^https?://(www\.)?x\.com", "https://twitter.com", url)
            return (
                f'<blockquote class="twitter-tweet"><a href="{esc(tweet)}"></a></blockquote>'
                '<script async src="https://platform.twitter.com/widgets.js"></script>'
            )
        if "google.com" in host and "/maps" in url:
            return f'<iframe class="notion-embed-frame" src="{esc(url)}&output=embed" loading="lazy"></iframe>'
        return None

    def bookmark_card(self, url, caption=None):
        meta = {"title": "", "description": "", "image": None, "icon": None}
        if self.web and url:
            try:
                meta = fetch_page_meta(url)
            except Exception as e:  # noqa: BLE001 - offline or blocked sites keep a plain card
                self.warnings.append(f"북마크 정보를 가져오지 못함 ({e}): {url}")
        title = meta["title"] or url
        cover = self.assets.fetch(meta["image"]) if meta.get("image") else None
        icon = self.assets.fetch(meta["icon"], quiet=True) if meta.get("icon") else None
        icon_html = f'<span class="notion-bookmark-icon" style="background-image:url(\'{esc(icon["url"])}\')"></span>' if icon else ""
        desc = f'<div class="notion-bookmark-desc">{esc(meta["description"])}</div>' if meta["description"] else ""
        cover_html = f'<div class="notion-bookmark-cover" style="background-image:url(\'{esc(cover["url"])}\')"></div>' if cover else ""
        card = (
            f'<a class="notion-bookmark" href="{esc(url)}" target="_blank" rel="noopener">'
            f'<div class="notion-bookmark-text"><div class="notion-bookmark-title">{esc(title)}</div>{desc}'
            f'<div class="notion-bookmark-url">{icon_html}<span>{esc(url)}</span></div></div>{cover_html}</a>'
        )
        return f'<div class="notion-bookmark-wrap">{card}{self.caption(caption)}</div>'

    def b_table(self, b, d):
        rows = []
        for ri, row in enumerate(b.get("_children") or []):
            cells = []
            for ci, cell in enumerate(row["table_row"]["cells"]):
                header = (ri == 0 and d.get("has_column_header")) or (ci == 0 and d.get("has_row_header"))
                tag = "th" if header else "td"
                cells.append(f"<{tag}>{self.rich_text(cell, md=False)}</{tag}>")
            row_html = "<tr>" + "".join(cells) + "</tr>"
            rows.append(f"<thead>{row_html}</thead>" if ri == 0 and d.get("has_column_header") else row_html)
        head = rows[:1] if d.get("has_column_header") else []
        body = rows[len(head):]
        return f'<table class="notion-table">{"".join(head)}<tbody>{"".join(body)}</tbody></table>'

    def b_column_list(self, b, d):
        cols = b.get("_children") or []
        ratios = [c["column"].get("width_ratio") or 1 / len(cols) for c in cols]
        total = sum(ratios) or 1
        parts = [
            md_div("notion-column", self.children(c), attrs=f' style="flex: {r / total:.4f} 1 0%"')
            for c, r in zip(cols, ratios)
        ]
        return md_div("notion-columns", "\n\n".join(parts))

    def b_synced_block(self, b, d):
        return self.children(b)

    def b_template(self, b, d):
        return None

    def b_breadcrumb(self, b, d):
        return None

    def b_table_of_contents(self, b, d):
        if not self.headings:
            return None
        top = min(level for level, _, _ in self.headings)
        links = "".join(
            f'<a class="notion-toc-item" style="padding-left: {(level - top) * 1.5}rem" href="#{esc(hid)}">{text}</a>'
            for level, hid, text in self.headings
        )
        return f'<nav class="notion-toc {color_class(d.get("color"))}">{links}</nav>'

    def b_child_page(self, b, d):
        return self.page_link(b["id"], d.get("title"))

    def b_link_to_page(self, b, d):
        if d.get("type") == "database_id":
            return self.page_link(d["database_id"], None, kind="database")
        return self.page_link(d.get("page_id") or d.get(d.get("type")), None)

    def b_child_database(self, b, d):
        try:
            return self.database(b["id"], d.get("title"))
        except NotionError as e:
            self.warnings.append(f"데이터베이스 '{d.get('title')}'를 읽지 못함: {e}")
            return self.page_link(b["id"], d.get("title"), kind="database")

    # ---- pages, icons ----------------------------------------------------- #

    def page_info(self, page_id):
        if page_id not in self.page_cache:
            try:
                page = self.client.call("GET", f"/pages/{page_id}")
                title = next((plain(p["title"]) for p in page["properties"].values() if p["type"] == "title"), "")
                self.page_cache[page_id] = (title, page.get("icon"))
            except NotionError:
                self.page_cache[page_id] = ("", None)
        return self.page_cache[page_id]

    def page_link(self, page_id, title, kind="page"):
        icon = None
        if kind == "page" and title is None:
            title, icon = self.page_info(page_id)
        icon_html = self.icon_html(icon) or ""
        default_icon = "notion-page-link-db" if kind == "database" else "notion-page-link-doc"
        icon_span = f'<span class="notion-page-link-icon">{icon_html}</span>' if icon_html else f'<span class="notion-page-link-icon {default_icon}"></span>'
        return (
            f'<a class="notion-page-link" href="{notion_url(page_id)}">{icon_span}'
            f'<span class="notion-page-link-title">{esc(title or "제목 없음")}</span></a>'
        )

    def icon_html(self, icon):
        if not icon:
            return ""
        if icon.get("type") == "emoji":
            return esc(icon["emoji"])
        url = file_url(icon) or (icon.get("custom_emoji") or {}).get("url")
        if not url:
            return ""
        asset = self.assets.fetch(url)
        return f'<span class="notion-icon-img" style="background-image:url(\'{esc(asset["url"] if asset else url)}\')"></span>'

    # ---- databases -------------------------------------------------------- #

    def database(self, db_id, fallback_title):
        db = self.client.call("GET", f"/databases/{db_id}")
        title = self.rich_text(db.get("title"), md=False) or esc(fallback_title or "")
        sources = db.get("data_sources") or []
        tables = []
        for source in sources:
            schema = self.client.call("GET", f"/data_sources/{source['id']}")["properties"]
            rows = paginate(self.client, "POST", f"/data_sources/{source['id']}/query", {})
            tables.append(self.db_table(schema, rows, source.get("name") if len(sources) > 1 else None))
        if not sources:  # older API responses keep the schema on the database itself
            rows = paginate(self.client, "POST", f"/databases/{db_id}/query", {})
            tables.append(self.db_table(db.get("properties", {}), rows, None))
        head = f'<div class="notion-db-title">{title}</div>' if title else ""
        return f'<div class="notion-db">{head}{"".join(tables)}</div>'

    def db_table(self, schema, rows, name):
        props = [(k, v) for k, v in schema.items() if v["type"] != "button"]
        props.sort(key=lambda kv: kv[1]["type"] != "title")
        head = "".join(f'<th class="notion-db-th-{p["type"]}">{esc(k)}</th>' for k, p in props)
        body = []
        for row in rows:
            cells = []
            for key, p in props:
                value = row["properties"].get(key)
                cells.append(f'<td class="notion-db-td-{p["type"]}">{self.prop_value(value, p) if value else ""}</td>')
            body.append("<tr>" + "".join(cells) + "</tr>")
        label = f'<div class="notion-db-view">{esc(name)}</div>' if name else ""
        return f'{label}<table class="notion-table notion-db-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'

    def pill(self, option):
        if not option:
            return ""
        return f'<span class="notion-tag notion-tag-{option.get("color", "default")}">{esc(option.get("name", ""))}</span>'

    def user_name(self, user):
        if user.get("name"):
            return user["name"]
        uid = user.get("id")
        if uid not in self.user_cache:
            try:
                self.user_cache[uid] = self.client.call("GET", f"/users/{uid}").get("name") or ""
            except NotionError:
                self.user_cache[uid] = ""
        return self.user_cache[uid]

    def prop_value(self, v, schema=None):
        t = v.get("type")
        val = v.get(t)
        if t in ("title", "rich_text"):
            text = self.rich_text(val, md=False)
            if t == "title":
                return f'<span class="notion-db-row-title">{text}</span>'
            return text
        if t == "number":
            return esc(self.format_number(val, (schema or {}).get("number", {}).get("format")))
        if t in ("select", "status"):
            return self.pill(val)
        if t == "multi_select":
            return "".join(self.pill(o) for o in val or [])
        if t == "date":
            if not val:
                return ""
            out = format_date(val.get("start"))
            return esc(out + (f" → {format_date(val['end'])}" if val.get("end") else ""))
        if t in ("people",):
            return ", ".join(esc(self.user_name(u)) for u in val or [])
        if t in ("created_by", "last_edited_by"):
            return esc(self.user_name(val or {}))
        if t in ("created_time", "last_edited_time"):
            return esc(format_date(val))
        if t == "checkbox":
            return f'<span class="notion-checkbox{" checked" if val else ""}"></span>'
        if t == "url":
            return f'<a href="{esc(val)}">{esc(val)}</a>' if val else ""
        if t == "email":
            return f'<a href="mailto:{esc(val)}">{esc(val)}</a>' if val else ""
        if t == "phone_number":
            return f'<a href="tel:{esc(val)}">{esc(val)}</a>' if val else ""
        if t == "files":
            links = []
            for f in val or []:
                asset = self.assets.fetch(file_url(f), name_hint=f.get("name"))
                links.append(f'<a href="{esc(asset["url"] if asset else file_url(f) or "")}">{esc(f.get("name", "file"))}</a>')
            return ", ".join(links)
        if t == "formula":
            ft = val.get("type")
            inner = val.get(ft)
            if ft == "date":
                return esc(format_date((inner or {}).get("start")))
            if ft == "boolean":
                return f'<span class="notion-checkbox{" checked" if inner else ""}"></span>'
            return esc("" if inner is None else str(inner))
        if t == "relation":
            titles = []
            for rel in val or []:
                title, _ = self.page_info(rel["id"])
                titles.append(f'<a class="notion-db-relation" href="{notion_url(rel["id"])}">{esc(title or "제목 없음")}</a>')
            return " ".join(titles)
        if t == "rollup":
            rt = val.get("type")
            if rt == "array":
                return " ".join(self.prop_value(item) for item in val.get("array") or [])
            if rt == "date":
                return esc(format_date((val.get("date") or {}).get("start")))
            return esc("" if val.get(rt) is None else str(val.get(rt)))
        if t == "unique_id":
            return esc(f"{val.get('prefix') + '-' if val.get('prefix') else ''}{val.get('number')}")
        if t == "verification":
            return esc((val or {}).get("state", ""))
        return ""

    @staticmethod
    def format_number(n, fmt):
        if n is None:
            return ""
        fmt = fmt or "number"
        if fmt == "percent":
            return f"{n * 100:g}%"
        symbols = {"won": "₩", "dollar": "$", "euro": "€", "yen": "¥", "pound": "£", "yuan": "CN¥"}
        text = f"{n:,}" if fmt != "number" else f"{n:g}"
        return symbols.get(fmt, "") + text


# --------------------------------------------------------------------------- #
# Front matter / output
# --------------------------------------------------------------------------- #


def yaml_value(v):
    if isinstance(v, dt.datetime):
        return f"{v:%Y-%m-%d %H:%M:%S %z}"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return json.dumps(str(v), ensure_ascii=False)


def split_front_matter(text):
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return [], text
    entries, current = [], None
    for line in m.group(1).split("\n"):
        km = re.match(r"([A-Za-z_][\w-]*):", line)
        if km:
            current = [km.group(1), [line]]
            entries.append(current)
        elif current:
            current[1].append(line)
    return entries, text[m.end():]


def build_front_matter(existing, values):
    lines, seen = [], set()
    for key, raw in existing:
        seen.add(key)
        if key in values:
            if values[key] is not None:
                lines.append(f"{key}: {yaml_value(values[key])}")
        else:
            lines.extend(raw)
    for key, value in values.items():
        if key not in seen and value is not None:
            lines.append(f"{key}: {yaml_value(value)}")
    return "---\n" + "\n".join(lines) + "\n---\n"


def page_property(page, field):
    for name, prop in page.get("properties", {}).items():
        if name.lower() not in PROPERTY_ALIASES[field]:
            continue
        t = prop["type"]
        val = prop.get(t)
        if t == "multi_select":
            return [o["name"] for o in val or []]
        if t in ("select", "status"):
            return [val["name"]] if val else []
        if t == "rich_text":
            return plain(val)
        if t == "date":
            return (val or {}).get("start")
    return None


def to_list(value):
    if value is None:
        return None
    if isinstance(value, list):
        return value
    return [s.strip() for s in str(value).split(",") if s.strip()]


def post_datetime(value, fallback):
    raw = value or fallback
    d = dt.datetime.fromisoformat(raw.replace("Z", "+00:00").replace(" ", "T", 1)) if "T" in raw or " " in raw else dt.datetime.fromisoformat(raw)
    if d.tzinfo is None:
        d = d.replace(tzinfo=KST)
    return d.astimezone(KST)


def find_existing(page_id):
    pattern = re.compile(rf"^notion_id:\s*[\"']?{re.escape(page_id)}[\"']?\s*$", re.M)
    for folder in ("_posts", "_drafts"):
        for path in sorted((ROOT / folder).glob("*.md")):
            head = path.read_text(encoding="utf-8")[:4000]
            if pattern.search(head):
                return path
    return None


def main():
    ap = argparse.ArgumentParser(description="노션 페이지를 Chirpy 블로그 글로 가져옵니다.")
    ap.add_argument("page", help="노션 페이지 URL 또는 ID")
    ap.add_argument("--draft", action="store_true", help="_drafts/에 저장 (발행하지 않음)")
    ap.add_argument("--slug", help="글 주소에 쓸 이름 (기본: 노션 제목)")
    ap.add_argument("--date", help='작성 시각, 예: "2026-10-01 14:00" (기본: 노션 속성 또는 페이지 생성 시각)')
    ap.add_argument("--categories", help='쉼표로 구분, 예: "보안,웹"')
    ap.add_argument("--tags", help='쉼표로 구분, 예: "xss,csp"')
    ap.add_argument("--out", help="블로그 대신 이 디렉터리에 index.md + assets/로 저장")
    ap.add_argument("--no-web", action="store_true", help="북마크 미리보기·임베드 확인용 외부 요청 생략")
    ap.add_argument("--record", help="Notion API 응답을 이 JSON 파일로 저장 (디버깅용)")
    ap.add_argument("--replay", help="저장해 둔 응답으로 변환만 수행 (토큰 불필요)")
    args = ap.parse_args()

    page_id = parse_page_id(args.page)
    record = {} if args.record else None
    if args.replay:
        client = ReplayClient(args.replay)
    else:
        token = os.environ.get("NOTION_TOKEN")
        if not token:
            raise SystemExit("NOTION_TOKEN 환경변수가 필요합니다. 예: export NOTION_TOKEN=ntn_...")
        client = NotionClient(token, record)

    try:
        log(f"노션 페이지 읽는 중: {page_id}")
        page = client.call("GET", f"/pages/{page_id}")
        blocks = fetch_tree(client, page_id, [0])
        log("")
    except NotionError as e:
        raise SystemExit(str(e))

    title = next((plain(p["title"]) for p in page["properties"].values() if p["type"] == "title"), "") or "제목 없음"
    existing = None if args.out else find_existing(page_id)
    existing_fm, _ = split_front_matter(existing.read_text(encoding="utf-8")) if existing else ([], "")
    existing_values = {k: "\n".join(raw) for k, raw in existing_fm}

    slug = args.slug or page_property(page, "slug") or slugify(title) or page_id.replace("-", "")[:8]
    date_value = args.date or page_property(page, "date")
    if date_value or not existing or "date" not in existing_values:
        when = post_datetime(date_value, page["created_time"])
    else:
        when = None  # keep the date already in the post

    if args.out:
        out_dir = Path(args.out).resolve()
        post_path = out_dir / "index.md"
        asset_dir = out_dir / "assets"
        url_prefix = "assets/"
    else:
        if args.draft:
            post_path = ROOT / "_drafts" / f"{slug}.md"
        elif existing and not (args.slug or args.date or existing.parent.name == "_drafts"):
            post_path = existing
        else:
            stamp = when or post_datetime(None, page["created_time"])
            post_path = ROOT / "_posts" / f"{stamp:%Y-%m-%d}-{slug}.md"
        asset_dir = ROOT / "assets" / "img" / "notion" / page_id.replace("-", "")
        url_prefix = f"/assets/img/notion/{page_id.replace('-', '')}/"

    stage = asset_dir.parent / f".{asset_dir.name}.tmp"
    shutil.rmtree(stage, ignore_errors=True)
    assets = Assets(stage, url_prefix)
    conv = Converter(client, assets, web=not args.no_web)
    try:
        log("변환 중...")
        conv.collect_headings(blocks)
        body = conv.render_blocks(blocks)
        cover = assets.fetch(file_url(page.get("cover")), name_hint="cover")
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    values = {
        "title": title,
        "date": when,
        "categories": to_list(args.categories) or page_property(page, "categories"),
        "tags": to_list(args.tags) or page_property(page, "tags"),
        "description": page_property(page, "description") or None,
        "image": {"path": cover["url"], "alt": title} if cover else None,
        "math": True if conv.uses_math else None,
        "mermaid": True if conv.uses_mermaid else None,
        "render_with_liquid": False,
        "notion_id": page_id,
        "notion_url": page.get("url") or notion_url(page_id),
        "notion_last_edited": page.get("last_edited_time"),
    }
    for key in ("categories", "tags", "description"):
        if values[key] is None and key not in existing_values:
            values[key] = [] if key != "description" else None
        elif values[key] is None:
            del values[key]  # keep what is already in the post
    for key in ("date",):
        if values[key] is None:
            del values[key]

    content = build_front_matter(existing_fm, values) + "\n" + md_div("notion-page", body) + "\n"

    post_path.parent.mkdir(parents=True, exist_ok=True)
    post_path.write_text(content, encoding="utf-8")
    if existing and existing != post_path:
        existing.unlink()
    shutil.rmtree(asset_dir, ignore_errors=True)
    if stage.exists():
        stage.rename(asset_dir)

    if args.record:
        Path(args.record).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")

    for w in conv.warnings + assets.warnings:
        log(f"⚠️  {w}")
    rel = lambda p: p.relative_to(ROOT) if p.is_relative_to(ROOT) else p  # noqa: E731
    log(f"\n완료: {rel(post_path)}")
    log(f"첨부 {len(assets.used)}개: {rel(asset_dir)}/" if assets.used else "첨부 파일 없음")


if __name__ == "__main__":
    main()
