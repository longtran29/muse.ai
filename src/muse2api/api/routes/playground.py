"""Playground: a single self-contained page to type a prompt and make media.

The page is public like the dashboard; it asks for an API key in the browser and
calls ``/v1/*`` with it. Being served from the gateway's own origin is what makes
those calls possible at all: ``app.py`` only allows CORS for chrome-extension://.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["playground"])

_PAGE = Path(__file__).resolve().parents[2] / "web" / "playground.html"


@lru_cache(maxsize=1)
def _html() -> str:
    return _PAGE.read_text(encoding="utf-8")


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """The bare origin is what people type first; send it to the playground."""
    return RedirectResponse("/playground", status_code=307)


@router.get("/playground", response_class=HTMLResponse, include_in_schema=False)
async def playground() -> HTMLResponse:
    return HTMLResponse(_html(), headers={"Cache-Control": "no-cache",
                                          "X-Frame-Options": "DENY",
                                          "Referrer-Policy": "no-referrer"})
