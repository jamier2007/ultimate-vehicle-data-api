"""
UK Vehicle Data micro‑service (async, cached, typed).

Run locally for testing:
    uvicorn app.vehicle_service:app --reload --port 5001
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import json
from collections import OrderedDict
from typing import Optional, Any

import httpx
from bs4 import BeautifulSoup
from cachetools import TTLCache, cached
from fastapi import FastAPI, HTTPException, Path, Query, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
import ast

# ────────────────────────── configuration ────────────────────────── #

BASE_URL = os.getenv(
    "TARGET_URL",
    "https://bookmygarage.com/garage-detail/"
    "sussexautocareltd/rh12lw/book/?ref=sussexautocare.co.uk&vrm={vrm}&referrer=widget",
)
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
RETRY_ATTEMPTS = int(os.getenv("HTTP_RETRIES", "3"))
CACHE_TTL = int(os.getenv("CACHE_TTL", 86_400))        # 24 h
CACHE_MAXSIZE = int(os.getenv("CACHE_MAXSIZE", "5000"))

VRM_RE = re.compile(r"^[A-Za-z0-9]{1,7}$")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("vehicle-service")

# ────────────────────────── FastAPI setup ────────────────────────── #

app = FastAPI(
    title="UK Vehicle Data API",
    version="2.0.0",
    description="Look up basic vehicle data by UK registration mark (VRM).",
)

# Set up static files directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

http_client: httpx.AsyncClient | None = None


@app.on_event("startup")
async def _startup() -> None:
    global http_client
    http_client = httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        http2=True,
        follow_redirects=True,
    )
    logger.info("HTTP client initialised")


@app.on_event("shutdown")
async def _shutdown() -> None:
    await http_client.aclose()  # type: ignore[attr-defined]
    logger.info("HTTP client closed")


# ────────────────────────── models ────────────────────────── #

class RepairQuote(BaseModel):
    hours: float = Field(..., alias="Hours")
    product_id: int = Field(..., alias="ProductId")
    parts_price: float = Field(..., alias="PartsPrice")

class PreviousOwner(BaseModel):
    date_of_transaction: str = Field(..., alias="DateOfTransaction")
    date_of_last_keeper_change: str = Field(..., alias="DateOfLastKeeperChange")
    number_of_previous_keepers: int = Field(..., alias="NumberOfPreviousKeepers")

class VehicleInfo(BaseModel):
    data: dict[str, Any]

    model_config = {
        "extra": "allow"
    }


# ────────────────────────── caching ────────────────────────── #

cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)


# ─────────────────────── helper functions ────────────────────── #

async def _fetch_html(vrm: str) -> str:
    assert http_client, "HTTP client not ready"
    url = BASE_URL.format(vrm=vrm)
    last_exc: Exception | None = None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            r = await http_client.get(url)
            r.raise_for_status()
            logger.debug("Response status: %d", r.status_code)
            logger.debug("Response headers: %s", dict(r.headers))
            logger.debug("Response content length: %d", len(r.text))
            logger.debug("Response content preview: %s", r.text[:500])
            return r.text
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            logger.warning("Attempt %d/%d failed for %s: %s",
                           attempt, RETRY_ATTEMPTS, vrm, exc)
            await asyncio.sleep(1)

    raise HTTPException(status_code=502,
                        detail=f"Upstream request failed: {last_exc}")


def _extract_json_object(html: str, key: str) -> dict[str, Any]:
    """Extract a JSON object that starts after a given key in raw HTML.

    This avoids brittle regex and instead finds the opening brace after
    the key and then counts braces while respecting JSON string quoting
    rules so that nested objects are handled correctly.
    """
    # Try both plain and escaped versions of the key ("VrmDetails" vs \"VrmDetails\")
    idx = html.find(f'"{key}"')
    if idx == -1:
        idx = html.find(f'\\"{key}\\"')  # escaped within a JS string
    if idx == -1:
        raise ValueError(f"Key '{key}' not found in document")

    # Advance to first '{' after the key
    start = html.find('{', idx)
    if start == -1:
        raise ValueError(f"Opening brace for key '{key}' not found")

    brace_level = 0
    in_string = False
    escaped = False
    for pos in range(start, len(html)):
        ch = html[pos]

        if ch == '"' and not escaped:
            in_string = not in_string
        if not in_string:
            if ch == '{':
                brace_level += 1
            elif ch == '}':
                brace_level -= 1
                if brace_level == 0:
                    json_str = html[start:pos + 1]
                    return _safe_json_load(json_str)
        # Track escape characters inside strings
        if ch == '\\' and not escaped:
            escaped = True
        else:
            escaped = False

    raise ValueError(f"Could not find matching closing brace for key '{key}'")


def _parse_html(html: str, vrm: str) -> dict[str, Any]:
    # Look for the VrmDetails object in the HTML (embedded JavaScript)
    logger.debug("Parsing HTML response for VRM: %s", vrm)

    try:
        data = _extract_json_object(html, 'VrmDetails')
        logger.debug("Extracted VrmDetails JSON: %s", data)
        return data
    except Exception as exc:
        logger.warning("Failed to extract VrmDetails using brace counting: %s", exc)

    # Fallback to previous (less reliable) regex extraction as a last resort
    vrm_match = re.search(r'"VrmDetails"\s*:\s*({.*?})', html, re.DOTALL)
    if vrm_match:
        try:
            json_str = vrm_match.group(1)
            data = _safe_json_load(json_str)
            logger.debug("Extracted VrmDetails via regex fallback: %s", data)
            return data
        except json.JSONDecodeError as exc:
            logger.warning("Regex fallback JSON decode error: %s", exc)

    logger.error("No vehicle data found in response for VRM: %s", vrm)
    raise HTTPException(404, f"No vehicle data found for {vrm}")


async def get_vehicle_info(vrm: str) -> dict[str, Any]:
    if vrm in cache:
        return cache[vrm]

    html = await _fetch_html(vrm)
    info = _parse_html(html, vrm)
    cache[vrm] = info
    return info


def _safe_json_load(json_str: str) -> dict[str, Any]:
    """Attempt to json.loads with a couple of fallback clean-ups."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        # Sometimes the chunk is still JavaScript-escaped (e.g. \" quotes)
        try:
            unescaped = bytes(json_str, "utf-8").decode("unicode_escape")
            return json.loads(unescaped)
        except Exception:
            raise exc


# ────────────────────────── routes ────────────────────────── #

@app.get("/", response_class=HTMLResponse, summary="Homepage")
async def home():
    """Return the HTML homepage for the vehicle lookup service."""
    html_file = os.path.join(static_dir, "index.html")
    
    # Check if index.html exists, if not return a basic HTML response
    if os.path.exists(html_file):
        with open(html_file, "r") as f:
            return f.read()
    else:
        return """
        <html>
            <head><title>UK Vehicle Lookup Service</title></head>
            <body>
                <h1>UK Vehicle Lookup Service</h1>
                <p>Please create the static/index.html file.</p>
            </body>
        </html>
        """

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon if available, otherwise return a 204 no content response."""
    favicon_path = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return Response(status_code=204)

@app.get("/{vrm}", summary="Look up a VRM")
async def lookup(
    vrm: str = Path(..., regex=r"^[A-Za-z0-9]{1,7}$",
                    description="Registration mark (no spaces)"),
    debug: bool = Query(False, description="Return debug info if true")
) -> Response:
    vrm = vrm.upper()
    if not VRM_RE.fullmatch(vrm):
        raise HTTPException(400, "Invalid registration format")

    logger.info("Lookup: %s", vrm)
    try:
        info = await get_vehicle_info(vrm)
        lines = [f"{k}: {v}" for k, v in info.items()]
        return Response("\n".join(lines), media_type="text/plain")
    except HTTPException as e:
        if debug:
            # Try to extract and show the raw chunk for debugging
            html = await _fetch_html(vrm)
            idx = html.find('"VrmDetails"')
            if idx == -1:
                idx = html.find('\\"VrmDetails\\"')
            start = html.find('{', idx)
            end = start
            brace = 0; in_str = False; esc = False
            for i, ch in enumerate(html[start:], start):
                if ch == '"' and not esc:
                    in_str = not in_str
                if not in_str:
                    if ch == '{': brace += 1
                    elif ch == '}': brace -= 1
                    if brace == 0: end = i; break
                esc = (ch == '\\' and not esc)
            raw = html[start:end+1] if start != -1 and end != -1 else ''
            # Try ast.literal_eval as fallback
            try:
                pyobj = ast.literal_eval(raw)
                py_lines = [f"{k}: {v}" for k, v in pyobj.items()]
                return Response("\n".join(py_lines), media_type="text/plain")
            except Exception as ex:
                return Response(f"Extraction failed.\nError: {e.detail}\nRaw: {raw[:500]}\nLiteral eval error: {ex}", media_type="text/plain")
        raise


@app.get("/", summary="Service info")
def root() -> dict[str, object]:
    return {
        "name": "UK Vehicle Data API",
        "version": app.version,
        "example": "/AB12CDE",
        "docs": "/docs",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)