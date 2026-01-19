# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional
from renderer import render_article

app = FastAPI(title="Article Renderer")


class RenderRequest(BaseModel):
    article: Dict[str, Any]
    images: Optional[Dict[int, Dict[str, Any]]] = None


@app.post("/render")
def render(req: RenderRequest):
    html = render_article(req.article, req.images)
    return {
        "html": html
    }
