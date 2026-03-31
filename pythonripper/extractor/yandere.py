"""Main module for interacting with https://yande.re/ ."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import httpx

import pythonripper.extractor.toolbox.centralfunctions as cf
import pythonripper.extractor.toolbox.files as f
import pythonripper.extractor.toolbox.scraperclasses as scraper


@final
class YandereAPI(scraper.BooruScraper):
    API_URL = "https://yande.re/post.json"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?yande\.re/post/show/(\d+)"

    ME = "yandere"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        return True

    def format_tagname(self, tagname: str) -> str:
        return tagname.replace(" ", "_").replace(";", "%3B")

    async def does_this_exist(self, tagname: str) -> bool:
        params: dict[str, int | str] = {"limit": 50, "page": 1, "tags": self.format_tagname(tagname)}
        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params=params)
        return bool(res.json())

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")

            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params={"tags": f"id:{post_id}"})
            json_data = res.json()[0]

        download_url = json_data["file_url"]
        assert isinstance(download_url, str)
        extension = f.match_extension(download_url)
        assert extension
        return scraper.PostData(
            identifier=json_data["id"],
            filehash=json_data["md5"],
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=scraper.TagsData(
                tags=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tags"]).split(" ")],
            ),
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        more_files = True
        tagname = self.format_tagname(tagname)
        params: dict[str, int | str] = {"limit": 50, "page": 1, "tags": tagname}
        assert isinstance(params["page"], int)
        data: list[dict[Any, Any]] = []
        while more_files:
            if params["page"] > 100:
                last100id = data[-1]["id"]
                params["page"] = 1
                params["tags"] = f"{tagname}+id:<{last100id}"
                continue

            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)

            if res.status_code != 200:
                logging.error("[YANDERE] - Request status code %s :(", res.status_code)
                raise cf.ExtractorExitError("Request status code %s :(", res.status_code)

            data = res.json()
            for post in data:
                post_data = await self._get_post_data(json_data=post)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            more_files = bool(data)
            params["page"] += 1
