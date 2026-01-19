import os
import time
import uuid
import logging
from typing import Any, Dict, Optional, Union, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from renderer import render_article  # ✅ 就從 render.py 匯入


logger = logging.getLogger("article_render.app")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
_formatter = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(message)s")
_handler.setFormatter(_formatter)
if not logger.handlers:
    logger.addHandler(_handler)


def _rid() -> str:
    return uuid.uuid4().hex[:10]


# ===== Pydantic Request/Response =====
class Title(BaseModel):
    line1: str = ""
    line2: str = ""


class Block(BaseModel):
    type: str
    text: Optional[str] = None
    variant: Optional[str] = None

    primary: Optional[str] = None
    secondary: Optional[str] = None

    id: Optional[Union[int, str]] = None
    purpose: Optional[str] = None
    ratio: Optional[str] = None

    title: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None

    leading_break: Optional[bool] = False


class Article(BaseModel):
    title: Title = Field(default_factory=Title)
    content: List[Block] = Field(default_factory=list)


class RenderRequest(BaseModel):
    article: Article
    images: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class RenderResponse(BaseModel):
    html: str
    report: Dict[str, Any]
    request_id: str


app = FastAPI(title="Article JSON -> HTML Renderer", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"ok": True, "service": "article-render", "version": "1.1.0"}


@app.post("/render", response_model=RenderResponse)
def render_endpoint(req: RenderRequest):
    request_id = _rid()
    t0 = time.time()

    article_dict = req.article.model_dump()
    images_dict = req.images or {}

    html, report = render_article(article_dict, images_dict, request_id=request_id)

    logger.info(
        f"[RID={request_id}] /render "
        f"ok={report.get('ok')} "
        f"unknown_types={len(report.get('unknown_block_types', []))} "
        f"missing_images={len(report.get('missing_image_slots', []))} "
        f"input_has_literal_backslash_n={report.get('input_has_literal_backslash_n')} "
        f"input_has_real_newline={report.get('input_has_real_newline')} "
        f"html_len={len(html)} "
        f"ms={int((time.time()-t0)*1000)}"
    )

    return RenderResponse(html=html, report=report, request_id=request_id)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
