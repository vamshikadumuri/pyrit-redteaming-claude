from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)
_env.filters["pct"] = lambda v: f"{(v or 0) * 100:.0f}%"


def render(name: str, **ctx) -> str:
    request = ctx.pop("request", None)
    ctx.setdefault("current_path", str(request.url.path) if request else "/")
    return _env.get_template(name).render(**ctx)
