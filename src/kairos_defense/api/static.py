"""Serve the built web app (SPEC §16.6, D-112): files from ``web/dist``, ``index.html`` for any
other path (client-side routes). ``/api/*`` and ``/ws/*`` never fall back to the app."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_web(app: FastAPI, dist: Path | str) -> None:
    root = Path(dist).resolve()
    index = root / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"{index} is missing: run `npm --prefix web run build`")

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str) -> FileResponse:
        if path == "api" or path.startswith(("api/", "ws/")):
            raise HTTPException(404, f"no route /{path}")
        target = (root / path).resolve()
        if path and target.is_file() and root in target.parents:
            hashed = "/assets/" in f"/{path}"  # Vite's content-hashed files
            cache = "public, max-age=31536000, immutable" if hashed else "no-cache"
            return FileResponse(target, headers={"Cache-Control": cache})
        if path.startswith("assets/") or Path(path).suffix:
            raise HTTPException(404, f"no file /{path}")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
