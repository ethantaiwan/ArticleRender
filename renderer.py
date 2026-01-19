# renderer.py
from typing import List, Dict, Any


def render_article(article: Dict[str, Any], images: Dict[int, Dict[str, Any]] | None = None) -> str:
    html = []

    # ---------- TITLE ----------
    title = article["title"]
    html.append(
        f"""
<h1 style="font-weight: 800; margin-bottom: 20px; font-size: 30px; line-height: 1.4; color: #111;">
{title["line1"]}<br>{title["line2"]}
</h1>
""".strip()
    )

    # ---------- CONTENT ----------
    for block in article["content"]:
        t = block["type"]

        if t == "p":
            html.append(f"<p>{block['text']}</p>")

        elif t == "h2":
            html.append(
                f"""<h2 style="font-weight: 800; color: #222; font-size: 24px; margin-bottom: 20px;">
{block['text']}
</h2>"""
            )

        elif t == "h3":
            html.append(
                f"""<h3 style="font-weight: bold; color: #444; margin-top: 30px;">
{block['text']}
</h3>"""
            )

        elif t == "blockquote":
            html.append(
                f"""
<blockquote style="border-left: 6px solid #d32f2f; background-color: #fff5f5; padding: 20px; margin: 30px 0; font-size: 1.1em; border-radius: 0 8px 8px 0;">
<strong>「{block['primary']}」</strong>
<br>
<span style="font-size: 0.9em; color: #666; margin-top: 10px; display: block;">
—— {block['secondary']}
</span>
</blockquote>
""".strip()
            )

        elif t == "info_card":
            html.append(
                f"""
<div style="background-color: #f1f8e9; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 0.95em;">
<strong>{block['title']}</strong><br>{block['text']}
</div>
""".strip()
            )

        elif t == "truth_list":
            items = []
            for i in block["items"]:
                icon = "❌" if i["kind"] == "myth" else "✅"
                color = "#d32f2f" if i["kind"] == "myth" else "#2e7d32"
                items.append(
                    f'<li style="margin-bottom: 10px; color: {color}; font-weight: bold;">{icon} {i["text"]}</li>'
                )
            html.append(
                f"""
<ul style="list-style-type: none; padding-left: 0;">
{''.join(items)}
</ul>
""".strip()
            )

        elif t == "calculation_card":
            html.append(
                f"""
<div style="border: 2px dashed #ccc; padding: 20px; border-radius: 10px; text-align: center; margin: 30px 0;">
<p style="margin: 0; font-size: 1.1em;"><strong>{block['formula']}</strong></p>
<p style="color: #666; font-size: 0.9em; margin-top: 5px;">{block['note']}</p>
</div>
""".strip()
            )

        elif t == "image_slot":
            if not images or block["id"] not in images:
                html.append(f"<!-- IMAGE {block['id']} MISSING -->")
            else:
                img = images[block["id"]]
                html.append(
                    f"""
<img src="{img['url']}"
     width="{img['width']}"
     height="{img['height']}"
     alt="{img['alt']}"
     style="width:100%; border-radius:8px; margin:30px 0;">
""".strip()
                )

        elif t == "hr":
            html.append('<hr style="margin: 50px 0; border: 0; border-top: 1px solid #eee;">')

        else:
            html.append(f"<!-- UNKNOWN BLOCK TYPE: {t} -->")

    # ---------- HERO QUOTE ----------
    hero = article.get("hero_quote")
    if hero:
        html.append(
            f"""
<div style="background-color: #333; color: #fff; padding: 25px; border-radius: 8px; text-align: center; margin: 30px 0;">
<h3 style="margin: 0 0 10px 0; color: #fff;">「{hero['zh']}」</h3>
<p style="margin: 0; font-size: 0.9em; opacity: 0.9;">{hero['en']}</p>
</div>
""".strip()
        )

    return "\n\n".join(html)
