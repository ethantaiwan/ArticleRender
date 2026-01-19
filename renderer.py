# renderer.py
from typing import Dict, Any, Optional


BASE_WRAPPER_STYLE = (
    "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; "
    "line-height: 1.8; color: #333; max-width: 800px; margin: 0 auto;"
)


def _normalize_text(s: Any) -> str:
    """
    Fix common LLM/json escaping issues.
    - Turn literal '\\n' into real newlines
    - Normalize Windows newlines
    - Keep real newlines if present (later can convert to <br> where needed)
    """
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)

    # literal backslash-n => newline
    s = s.replace("\\n", "\n")

    # windows newline
    s = s.replace("\r\n", "\n").replace("\r", "\n")

    return s


def _text_to_html_inline(s: str) -> str:
    """
    Convert remaining newlines in a block into <br>.
    Keep it simple & deterministic.
    NOTE: This assumes you trust the text (or you control generation).
    If you need security hardening, add an allowlist sanitizer for <strong><br>.
    """
    s = _normalize_text(s)
    # For inline formatting, turn newlines into <br>
    s = s.replace("\n", "<br>")
    return s


def render_article(article: Dict[str, Any], images: Optional[Dict[Any, Dict[str, Any]]] = None) -> str:
    html = []

    # ---- wrapper (NOT <article>, but keeps identical base look) ----
    html.append(f'<div style="{BASE_WRAPPER_STYLE}">')

    # ---- title ----
    title = article.get("title", {})
    line1 = _text_to_html_inline(title.get("line1", ""))
    line2 = _text_to_html_inline(title.get("line2", ""))
    html.append(
        f"""
<h1 style="font-weight: 800; margin-bottom: 20px; font-size: 30px; line-height: 1.4; color: #111;">
{line1}<br>{line2}
</h1>
""".strip()
    )

    # ---- content blocks ----
    for block in article.get("content", []):
        t = block.get("type")

        if t == "p":
            txt = _text_to_html_inline(block.get("text", ""))
            html.append(f"<p>{txt}</p>")

        elif t == "h2":
            txt = _text_to_html_inline(block.get("text", ""))
            # 你原版 h2 前面常有 <br> 造成視覺間距
            leading_break = block.get("leading_break", False)
            br = "<br>" if leading_break else ""
            html.append(
                f"""<h2 style="font-weight: 800; color: #222; font-size: 24px; margin-bottom: 20px;">
{br}{txt}</h2>"""
            )

        elif t == "h3":
            txt = _text_to_html_inline(block.get("text", ""))
            html.append(
                f"""<h3 style="font-weight: bold; color: #444; margin-top: 30px;">{txt}</h3>"""
            )

        elif t == "hr":
            html.append('<hr style="margin: 50px 0; border: 0; border-top: 1px solid #eee;">')

        elif t == "blockquote":
            primary = _text_to_html_inline(block.get("primary", ""))
            secondary = _text_to_html_inline(block.get("secondary", ""))
            html.append(
                f"""
<blockquote style="border-left: 6px solid #d32f2f; background-color: #fff5f5; padding: 20px; margin: 30px 0; font-size: 1.1em; border-radius: 0 8px 8px 0;">
<strong>「{primary}」</strong> <br>
<span style="font-size: 0.9em; color: #666; margin-top: 10px; display: block;">—— {secondary}</span>
</blockquote>
""".strip()
            )

        elif t == "info_card":
            title_txt = _text_to_html_inline(block.get("title", ""))
            body_txt = _text_to_html_inline(block.get("text", ""))
            html.append(
                f"""
<div style="background-color: #f1f8e9; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 0.95em;">
<strong>{title_txt}</strong><br>{body_txt}
</div>
""".strip()
            )

        elif t == "truth_list":
            items_html = []
            for i in block.get("items", []):
                kind = i.get("kind")
                txt = _text_to_html_inline(i.get("text", ""))
                icon = "❌" if kind == "myth" else "✅"
                color = "#d32f2f" if kind == "myth" else "#2e7d32"
                items_html.append(
                    f'<li style="margin-bottom: 10px; color: {color}; font-weight: bold;">{icon} {txt}</li>'
                )
            html.append(
                f"""
<ul style="list-style-type: none; padding-left: 0;">
{''.join(items_html)}
</ul>
""".strip()
            )

        elif t == "calculation_card":
            formula = _text_to_html_inline(block.get("formula", ""))
            note = _text_to_html_inline(block.get("note", ""))
            html.append(
                f"""
<div style="border: 2px dashed #ccc; padding: 20px; border-radius: 10px; text-align: center; margin: 30px 0;">
<p style="margin: 0; font-size: 1.1em;"><strong>{formula}</strong></p>
<p style="color: #666; font-size: 0.9em; margin-top: 5px;">{note}</p>
</div>
""".strip()
            )

        elif t == "image_slot":
            slot_id = block.get("id")
            meta = None
            if images is not None and slot_id is not None:
                meta = images.get(slot_id) or images.get(str(slot_id))  # 兼容 int/str key

            if not meta:
                html.append(f"<!-- IMAGE {slot_id} MISSING -->")
            else:
                url = meta.get("url", "")
                alt = _text_to_html_inline(meta.get("alt", ""))
                width = meta.get("width", 1200)
                height = meta.get("height", 630)
                caption = meta.get("caption")
                html.append(
                    f"""
<img src="{url}"
     width="{width}"
     height="{height}"
     alt="{alt}"
     style="width:100%; border-radius:8px; margin:30px 0;">
""".strip()
                )
                if caption:
                    cap = _text_to_html_inline(caption)
                    html.append(f'<p style="color:#666; font-size: 0.9em; margin-top: -18px;">{cap}</p>')

        elif t == "hero_quote":
            zh = _text_to_html_inline(block.get("zh", ""))
            en = _text_to_html_inline(block.get("en", ""))
            html.append(
                f"""
<div style="background-color: #333; color: #fff; padding: 25px; border-radius: 8px; text-align: center; margin: 30px 0;">
<h3 style="margin: 0 0 10px 0; color: #fff;">「{zh}」</h3>
<p style="margin: 0; font-size: 0.9em; opacity: 0.9;">{en}</p>
</div>
""".strip()
            )

        else:
            html.append(f"<!-- UNKNOWN BLOCK TYPE: {t} -->")

    # close wrapper
    html.append("</div>")
    return "\n\n".join(html)
