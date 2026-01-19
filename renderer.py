import os
import json
import time
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# ============================================================
# Logging (Render logs)
# ============================================================
logger = logging.getLogger("article_render")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(message)s"
)
_handler.setFormatter(_formatter)
if not logger.handlers:
    logger.addHandler(_handler)


def _rid() -> str:
    return uuid.uuid4().hex[:10]


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


# ============================================================
# Pydantic Models
# ============================================================
class Block(BaseModel):
    type: str
    text: Optional[str] = None

    # blockquote
    variant: Optional[str] = None
    primary: Optional[str] = None
    secondary: Optional[str] = None

    # image_slot
    id: Optional[Union[int, str]] = None
    purpose: Optional[str] = None
    ratio: Optional[str] = None

    # info_card
    title: Optional[str] = None

    # truth_list
    items: Optional[List[Dict[str, Any]]] = None

    # hero_quote (as block)
    zh: Optional[str] = None
    en: Optional[str] = None

    # optional layout hint
    leading_break: Optional[bool] = False


class Title(BaseModel):
    line1: str = ""
    line2: str = ""


class HeroQuote(BaseModel):
    zh
