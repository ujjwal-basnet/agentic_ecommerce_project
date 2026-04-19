"""Render products.md from the DB via Jinja."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
import database

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(default=False),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def _parse_tags(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(t).strip() for t in parsed if str(t).strip()]
    except (ValueError, TypeError):
        pass
    return [t.strip() for t in text.split(",") if t.strip()]


def regenerate_products_md(path: str | Path | None = None) -> Path:
    """Pull all products from DB, render the Jinja template, and write products.md."""
    rows = database.get_all_products()
    products: list[dict] = []
    wearable_ids: list[int] = []
    for r in rows:
        rec = dict(r)
        rec["tag_list"] = _parse_tags(rec.get("tags"))
        products.append(rec)
        if rec.get("is_wearable"):
            wearable_ids.append(int(rec["id"]))

    out = _env.get_template("products.md.j2").render(
        products=products,
        wearable_ids=sorted(wearable_ids),
    )
    target = Path(path or config.PRODUCTS_MD_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(out, encoding="utf-8")
    logger.info("Regenerated %s (%d products)", target, len(products))
    return target
