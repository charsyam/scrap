from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bs4 import BeautifulSoup

import logging
from datetime import datetime
import httpx
import sys

from exceptions import UnicornException
from settings import Settings

from log import init_log
from cors import init_cors
from instrumentator import init_instrumentator
from config import Config
from localcache import LocalCache

import urllib.parse


app = FastAPI()
settings = Settings()
lc = LocalCache()

conf = Config(settings.CONFIG_PATH)

init_log(app, conf.section("log")["path"])
init_cors(app)
init_instrumentator(app)

typeconf = conf.section("type")

@app.exception_handler(UnicornException)
async def unicorn_exception_handler(request: Request, exc: UnicornException):
    return JSONResponse(
        status_code=exc.status,
        content={"code": exc.code, "message": exc.message},
    )

async def call_api(url: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        return r.text


def parse_opengraph(body: str):
    soup = BeautifulSoup(body, 'html.parser')

    title = soup.find("meta",  {"property":"og:title"})
    url = soup.find("meta",  {"property":"og:url"})
    og_type = soup.find("meta",  {"property":"og:type"})
    image = soup.find("meta",  {"property":"og:image"})
    description = soup.find("meta",  {"property":"og:description"})
    author = soup.find("meta",  {"property":"og:article:author"})

    resp = {}
    scrap = {}
    scrap["title"] = title["content"] if title else None
    scrap["url"] = url["content"] if url else None
    scrap["type"] = og_type["content"] if og_type else None
    scrap["image"] = image["content"] if image else None
    scrap["description"] = description["content"] if description else None
    scrap["author"] = author["content"] if author else None
    resp["scrap"] = scrap

    return resp

@app.get("/health_check")
async def health_check():
    return "OK"

@app.get("/api/v1/scrap/")
#@cache()
async def scrap(url: str):
    try:
        url = urllib.parse.unquote(url)
        resp = lc.get(url)
        if not resp:
            print("Not Cached: " + url)
            body = await call_api(url)
            resp = parse_opengraph(body)
            lc.put(url, resp, 120)

        resp["type"] = typeconf["type"]
        return resp
    except Exception as e:
        raise UnicornException(status=400, code=-20000, message=str(e))
