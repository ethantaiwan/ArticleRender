# render.py
# ============================================================
# ArticleValidator + HtmlRenderer + render_article()
# - Pure static HTML (no <html><body> wrapper)
# - Strong logging for Render
# ============================================================

from __future__ import annotations

import html
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("article_renderer")

# If app.py doesn't configure logging, this ensures something prints in Render logs.
if not logger.handlers:
    _h = logging.StreamHandler()
    _fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _h.setFormatter(_fmt)
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


# ----------------------------
# Helpers
# ----------------------------

def _safe_json(obj: Any, limit: int = 2000) -> str:
    """Safe stringify for logs (avoid huge blobs)."""
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = repr(obj)
    if len(s) > limit:
        return s[:limit] + f"...(truncated,len={len(s)})"
    return s


def _is_str(x: Any) -> bool:
    return isinstance(x, str)


def _normalize_text(s: str) -> str:
    """
    Normalize text coming from JSON:
    - Convert literal backslash-n sequences to real newlines
    - Normalize CRLF/CR to LF
    - Strip trailing spaces on each line (optional)
    """
    if not isinstance(s, str):
        return ""
    # literal "\n" -> newline
    s = s.replace("\\n", "\n")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


def _escape(s: str) -> str:
    """HTML escape."""
    return html.escape(s, quote=True)


def _inline_md_to_html(text: str) -> str:
    """
    Minimal inline markdown:
    - **bold** -> <strong>
    - Keep existing Chinese quotes etc.
    - Newlines are handled later globally; here we keep '\n' as-is.
    """
    text = _normalize_text(text)
    esc = _escape(text)

    # bold: **...**
    esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)

    return esc


def _text_with_breaks(text: str) -> str:
    """Convert text to HTML with <br> for newlines."""
    t = _inline_md_to_html(text)
    return t.replace("\n", "<br>")


def _style_article_container() -> str:
    return (
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;"
        "line-height: 1.8;"
        "color: #333;"
        "max-width: 800px;"
        "margin: 0 auto;"
    )


# ----------------------------
# Validation report
# ----------------------------

@dataclass
class ValidationReport:
    ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    unknown_block_types: List[str] = field(default_factory=list)
    missing_image_slots: List[int] = field(default_factory=list)

    input_has_literal_backslash_n: bool = False
    input_has_real_newline: bool = False

    def add_error(self, msg: str):
        self.ok = False
        self.errors.append(msg)

    def add_warn(self, msg: str):
        self.warnings.append(msg)


class ArticleValidator:
    """
    Validate article.json structure, detect missing images, unknown types,
    and common string escaping issues.
    """

    SUPPORTED_TYPES = {
        "p",
        "h1",
        "h2",
        "h3",
        "hr",
        "blockquote",
        "image_slot",
        "info_card",
        "truth_list",
        "icon_list",
        "highlight_box",
    }

    def validate(self, article: Dict[str, Any], images: Optional[Dict[str, Any]]) -> ValidationReport:
        rpt = ValidationReport()

        if not isinstance(article, dict):
            rpt.add_error("article must be an object")
            return rpt

        # title
        title = article.get("title")
        if title is not None and not isinstance(title, dict):
            rpt.add_error("article.title must be an object (or omitted)")

        # content
        content = article.get("content")
        if not isinstance(content, list):
            rpt.add_error("article.content must be a list")
            return rpt

        # detect "\n" patterns in input
        # (we scan only text-like fields)
        def scan_text_fields(x: Any):
            if isinstance(x, str):
                if "\\n" in x:
                    rpt.input_has_literal_backslash_n = True
                if "\n" in x:
                    rpt.input_has_real_newline = True
            elif isinstance(x, dict):
                for v in x.values():
                    scan_text_fields(v)
            elif isinstance(x, list):
                for v in x:
                    scan_text_fields(v)

        scan_text_fields(article)

        # validate blocks
        for i, blk in enumerate(content):
            if not isinstance(blk, dict):
                rpt.add_error(f"content[{i}] must be an object")
                continue

            t = blk.get("type")
            if t not in self.SUPPORTED_TYPES:
                rpt.unknown_block_types.append(str(t))
                rpt.add_warn(f"Unknown block type at content[{i}]: {t}")

            # required fields by type
            if t in {"p", "h1", "h2", "h3"}:
                if not _is_str(blk.get("text", "")):
                    rpt.add_error(f"content[{i}].text must be a string for type={t}")

            if t == "blockquote":
                if not _is_str(blk.get("primary", "")):
                    rpt.add_error(f"content[{i}].primary must be a string for blockquote")
                # secondary optional but if present must be str
                sec = blk.get("secondary")
                if sec is not None and not _is_str(sec):
                    rpt.add_error(f"content[{i}].secondary must be a string if provided")

            if t == "image_slot":
                slot_id = blk.get("id")
                if not isinstance(slot_id, int):
                    rpt.add_error(f"content[{i}].id must be an int for image_slot")
                else:
                    # images keys are strings in JSON by default
                    if images is None or (str(slot_id) not in images and slot_id not in images):
                        rpt.missing_image_slots.append(slot_id)

            if t == "info_card":
                if not _is_str(blk.get("title", "")):
                    rpt.add_error(f"content[{i}].title must be a string for info_card")
                if not _is_str(blk.get("text", "")):
                    rpt.add_error(f"content[{i}].text must be a string for info_card")

            if t == "truth_list":
                items = blk.get("items")
                if not isinstance(items, list) or len(items) == 0:
                    rpt.add_error(f"content[{i}].items must be a non-empty list for truth_list")

            if t == "icon_list":
                items = blk.get("items")
                if not isinstance(items, list) or len(items) == 0:
                    rpt.add_error(f"content[{i}].items must be a non-empty list for icon_list")

            if t == "highlight_box":
                if not _is_str(blk.get("text", "")):
                    rpt.add_error(f"content[{i}].text must be a string for highlight_box")

        return rpt


# ----------------------------
# Renderer
# ----------------------------

class HtmlRenderer:
    """
    Render the article structure into the target HTML style you showed.
    Returns ONLY the inner article HTML (no <html><body>).
    """

    def render(self, article: Dict[str, Any], images: Optional[Dict[str, Any]], request_id: str) -> str:
        out: List[str] = []
        out.append(f'<div style="{_style_article_container()}">')

        # Title
        title = article.get("title") or {}
        if isinstance(title, dict):
            line1 = _normalize_text(str(title.get("line1", "") or ""))
            line2 = _normalize_text(str(title.get("line2", "") or ""))
            full_title = ""
            if line1 and line2:
                full_title = f"{line1}<br>{line2}"
            else:
                full_title = line1 or line2

            if full_title:
                out.append(
                    '<h1 style="font-weight: 800; margin-bottom: 20px; font-size: 30px; line-height: 1.4; color: #111;">'
                    f"{_escape(full_title).replace('<br>', '<br>')}"
                    "</h1>"
                )

        # Optional hero_quote (big dark box)
        hero = article.get("hero_quote")
        if isinstance(hero, dict):
            zh = _normalize_text(str(hero.get("zh", "") or "")).strip()
            en = _normalize_text(str(hero.get("en", "") or "")).strip()
            if zh or en:
                out.append(
                    '<div style="background-color: #333; color: #fff; padding: 25px; border-radius: 12px; text-align: center; margin: 30px 0;">'
                )
                if zh:
                    out.append(f'<h3 style="margin: 0 0 10px 0; color: #fff; font-size: 22px;">「{_escape(zh)}」</h3>')
                if en:
                    out.append(f'<p style="margin: 0; font-size: 0.95em; opacity: 0.9;">{_escape(en)}</p>')
                out.append("</div>")

        # content blocks
        content = article.get("content", [])
        for idx, blk in enumerate(content):
            if not isinstance(blk, dict):
                out.append(f"<!-- INVALID_BLOCK content[{idx}] not an object -->")
                continue

            t = blk.get("type")
            try:
                out.extend(self._render_block(blk, images))
            except Exception as e:
                # Never hard-crash: log and leave a marker in HTML
                logger.exception(f"[RID={request_id}] render block failed idx={idx} type={t}: {e}")
                out.append(f"<!-- RENDER_ERROR idx={idx} type={_escape(str(t))} err={_escape(str(e))} -->")

        out.append("</div>")

        html_str = "\n".join(out)

        # Final safety: never leak literal "\n" (two chars) into output
        if "\\n" in html_str:
            logger.warning(f"[RID={request_id}] OUTPUT contains literal \\\\n; normalizing.")
            html_str = html_str.replace("\\n", "\n")

        # Convert real newlines inside text nodes were already converted to <br>,
        # but join() adds newlines between tags which is fine.
        return html_str

    def _render_block(self, blk: Dict[str, Any], images: Optional[Dict[str, Any]]) -> List[str]:
        t = blk.get("type")
        out: List[str] = []

        if t == "p":
            txt = _normalize_text(str(blk.get("text", "") or ""))
            out.append(f"<p>{_text_with_breaks(txt)}</p>")

        elif t == "h1":
            txt = _normalize_text(str(blk.get("text", "") or ""))
            out.append(
                '<h1 style="font-weight: 800; color: #222; font-size: 24px; margin-bottom: 20px;">'
                f"{_text_with_breaks(txt)}"
                "</h1>"
            )

        elif t == "h2":
            txt = _normalize_text(str(blk.get("text", "") or ""))
            out.append(
                '<h2 style="font-weight: 800; color: #222; font-size: 24px; margin-bottom: 20px;">'
                f"{_text_with_breaks(txt)}"
                "</h2>"
            )

        elif t == "h3":
            txt = _normalize_text(str(blk.get("text", "") or ""))
            out.append(
                '<h3 style="font-weight: bold; color: #444; margin-top: 30px;">'
                f"{_text_with_breaks(txt)}"
                "</h3>"
            )

        elif t == "hr":
            out.append('<hr style="margin: 50px 0; border: 0; border-top: 1px solid #eee;">')

        elif t == "blockquote":
            variant = str(blk.get("variant", "emphasis") or "emphasis")
            primary = _normalize_text(str(blk.get("primary", "") or "")).strip()
            secondary = _normalize_text(str(blk.get("secondary", "") or "")).strip()

            if variant == "emphasis":
                out.append(
                    '<blockquote style="border-left: 6px solid #d32f2f; background-color: #fff5f5; padding: 20px; margin: 30px 0; font-size: 1.1em; border-radius: 0 8px 8px 0;">'
                )
                if primary:
                    out.append(f"<strong>「{_escape(primary)}」</strong>")
                if secondary:
                    out.append(
                        f'<br><span style="font-size: 0.9em; color: #666; margin-top: 10px; display: block;">—— {_escape(secondary)}</span>'
                    )
                out.append("</blockquote>")
            else:
                # fallback
                out.append("<blockquote>")
                if primary:
                    out.append(f"<strong>{_escape(primary)}</strong>")
                if secondary:
                    out.append(f"<br><span>{_escape(secondary)}</span>")
                out.append("</blockquote>")

        elif t == "image_slot":
            # NOTE: we do NOT render "圖片X-生成" heading here.
            # We render the actual <img> if images are provided.
            slot_id = blk.get("id")
            key_str = str(slot_id)
            meta = None
            if images:
                meta = images.get(key_str) or images.get(slot_id)  # tolerate int key too

            if not meta:
                out.append(f"<!-- IMAGE_SLOT_MISSING id={_escape(key_str)} -->")
            else:
                url = str(meta.get("url", "") or "")
                alt = _normalize_text(str(meta.get("alt", "") or ""))
                width = int(meta.get("width", 1200) or 1200)
                height = int(meta.get("height", 630) or 630)
                caption = _normalize_text(str(meta.get("caption", "") or "")).strip()

                out.append(
                    f'<img src="{_escape(url)}" width="{width}" height="{height}" alt="{_escape(alt)}" '
                    'style="width: 100%; height: auto; border-radius: 10px; margin: 30px 0;">'
                )
                if caption:
                    out.append(
                        f'<p style="color: #666; font-size: 0.9em; margin-top: -18px; margin-bottom: 18px;">{_text_with_breaks(caption)}</p>'
                    )

        elif t == "info_card":
            variant = str(blk.get("variant", "green") or "green")
            title = _normalize_text(str(blk.get("title", "") or "")).strip()
            txt = _normalize_text(str(blk.get("text", "") or "")).strip()

            if variant == "green":
                out.append(
                    '<div style="background-color: #f1f8e9; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 0.95em;">'
                )
                if title:
                    out.append(f"<strong>{_escape(title)}</strong><br>")
                if txt:
                    out.append(f"{_text_with_breaks(txt)}")
                out.append("</div>")
            elif variant == "dashed_outline":
                out.append(
                    '<div style="border: 2px dashed #ccc; padding: 18px; border-radius: 10px; margin: 20px 0;">'
                )
                if title:
                    out.append(f"<strong>{_escape(title)}</strong><br>")
                if txt:
                    out.append(f"{_text_with_breaks(txt)}")
                out.append("</div>")
            else:
                out.append('<div style="padding: 15px; border-radius: 8px; margin: 20px 0; border: 1px solid #eee;">')
                if title:
                    out.append(f"<strong>{_escape(title)}</strong><br>")
                if txt:
                    out.append(f"{_text_with_breaks(txt)}")
                out.append("</div>")

        elif t == "truth_list":
            items = blk.get("items") or []
            out.append('<ul style="list-style-type: none; padding-left: 0; margin: 15px 0;">')
            for it in items:
                if not isinstance(it, dict):
                    continue
                kind = str(it.get("kind", "") or "")
                txt = _normalize_text(str(it.get("text", "") or "")).strip()
                if not txt:
                    continue
                if kind == "myth":
                    out.append(
                        '<li style="margin-bottom: 10px; color: #d32f2f; font-weight: bold;">'
                        f"❌ {_escape(txt)}"
                        "</li>"
                    )
                elif kind == "fact":
                    out.append(
                        '<li style="margin-bottom: 10px; color: #2e7d32; font-weight: bold;">'
                        f"✅ {_escape(txt)}"
                        "</li>"
                    )
                else:
                    out.append(f'<li style="margin-bottom: 10px;">• {_escape(txt)}</li>')
            out.append("</ul>")

        elif t == "icon_list":
            items = blk.get("items") or []
            out.append('<ul style="list-style: none; padding: 0; margin: 10px 0;">')
            for it in items:
                if not isinstance(it, dict):
                    continue
                icon = _normalize_text(str(it.get("icon", "") or "")).strip()
                title = _normalize_text(str(it.get("title", "") or "")).strip()
                txt = _normalize_text(str(it.get("text", "") or "")).strip()
                if not (icon or title or txt):
                    continue
                out.append('<li style="display: flex; align-items: flex-start; margin-bottom: 15px;">')
                out.append(f'<span style="font-size: 24px; margin-right: 15px; line-height: 1;">{_escape(icon)}</span>')
                out.append("<div>")
                if title:
                    out.append(f"<strong>{_escape(title)}</strong><br>")
                if txt:
                    out.append(f'<span style="color: #333;">{_text_with_breaks(txt)}</span>')
                out.append("</div></li>")
            out.append("</ul>")

        elif t == "highlight_box":
            variant = str(blk.get("variant", "dark_solid") or "dark_solid")
            txt = _normalize_text(str(blk.get("text", "") or "")).strip()
            if variant == "dark_solid":
                out.append(
                    '<div style="background-color: #333; color: #fff; padding: 18px 20px; border-radius: 12px; text-align: center; margin: 30px 0; font-weight: 800; font-size: 20px;">'
                    f"{_text_with_breaks(txt)}"
                    "</div>"
                )
            else:
                out.append(
                    '<div style="border: 2px solid #333; padding: 18px 20px; border-radius: 12px; text-align: center; margin: 30px 0; font-weight: 800; font-size: 20px;">'
                    f"{_text_with_breaks(txt)}"
                    "</div>"
                )

        else:
            out.append(f"<!-- UNKNOWN_BLOCK type={_escape(str(t))} -->")

        return out


# ----------------------------
# Public function used by app.py
# ----------------------------

_validator = ArticleValidator()
_renderer = HtmlRenderer()


def render_article(
    article: Dict[str, Any],
    images: Optional[Dict[str, Any]] = None,
    request_id: str = "NA",
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns:
      (html_string, report_dict)
    """
    t0 = time.perf_counter()

    # default images
    if images is None:
        images = {}

    # Validate
    rpt = _validator.validate(article, images)

    # Render
    html_str = _renderer.render(article, images, request_id=request_id)

    # Output sanity checks
    output_has_literal_backslash_n = ("\\n" in html_str)
    if output_has_literal_backslash_n:
        rpt.warnings.append("OUTPUT contains literal '\\n' (should not happen).")
        # best effort fix
        html_str = html_str.replace("\\n", "\n")

    ms = int((time.perf_counter() - t0) * 1000)

    report_dict = {
        "ok": rpt.ok,
        "errors": rpt.errors,
        "warnings": rpt.warnings,
        "unknown_block_types": rpt.unknown_block_types,
        "missing_image_slots": rpt.missing_image_slots,
        "input_has_literal_backslash_n": rpt.input_has_literal_backslash_n,
        "input_has_real_newline": rpt.input_has_real_newline,
        "output_has_literal_backslash_n": output_has_literal_backslash_n,
        "html_length": len(html_str),
        "render_ms": ms,
    }

    logger.info(
        f"[RID={request_id}] render ok={report_dict['ok']} "
        f"unknown_types={len(report_dict['unknown_block_types'])} "
        f"missing_images={len(report_dict['missing_image_slots'])} "
        f"in_lit_n={report_dict['input_has_literal_backslash_n']} "
        f"out_lit_n={report_dict['output_has_literal_backslash_n']} "
        f"html_len={report_dict['html_length']} ms={report_dict['render_ms']}"
    )

    if not rpt.ok:
        logger.warning(f"[RID={request_id}] validation errors: {rpt.errors}")
    if rpt.warnings:
        logger.warning(f"[RID={request_id}] warnings: {rpt.warnings}")
    if rpt.unknown_block_types:
        logger.warning(f"[RID={request_id}] unknown_block_types: {rpt.unknown_block_types}")
    if rpt.missing_image_slots:
        logger.warning(f"[RID={request_id}] missing_image_slots: {rpt.missing_image_slots}")

    return html_str, report_dict
