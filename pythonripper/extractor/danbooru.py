"""Main module for interacting with https://danbooru.donmai.us/ ."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import httpx

import pythonripper.extractor.toolbox.centralfunctions as cf
import pythonripper.extractor.toolbox.scraperclasses as scraper


@final
class DanbooruAPI(scraper.BooruScraper):
    API_TAG_URL = "https://danbooru.donmai.us/posts.json"
    API_POST_URL = "https://danbooru.donmai.us/posts/{post_id}.json"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?danbooru\.donmai\.us/posts/(\d+)"

    ME = "danbooru"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.random_tag_name = "random:1000"
        self.headers = self.download_headers = {"User-Agent": "Mozilla/5.0 (compatible)"}
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        return True

    async def does_this_exist(self, tag_name: str) -> bool:
        params: dict[str, str | int] = {"tags": self.format_tagname(tag_name)}
        await self.LIMIT.wait()
        res = await self.session.get(self.API_TAG_URL, params=params)
        return bool(res.json())

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post id nor json_data given (one is necessary).")
            res = await self.session.get(self.API_POST_URL.format(post_id=post_id))
            json_data = res.json()
        if post_id is None:
            post_id = str(json_data["id"])

        tags = scraper.TagsData(
            artists=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tag_string_artist"]).split(" ")],
            parodies=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tag_string_copyright"]).split(" ")],
            characters=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tag_string_character"]).split(" ")],
            tags=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tag_string_general"]).split(" ")],
            metatags=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tag_string_meta"]).split(" ")],
        )

        return scraper.PostData(
            identifier=post_id,
            filehash=str(json_data["md5"]),
            elements=scraper.PostElementLinks(download_url=json_data["file_url"], extension=json_data["file_ext"]),
            tags=tags,
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        truepage: int = 1
        more_files = True
        params: dict[str, str | int] = {"tags": tagname, "limit": 25, "page": 1}
        assert isinstance(params["page"], int)

        data: dict[Any, Any] = {}
        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_TAG_URL, params=params)

            try:
                if res.json()["success"] is False and res.json()["message"] == "The database timed out running your query.":
                    logging.warning("Timeouted... trying again: %s %s .", self.API_TAG_URL, params)
                    await asyncio.sleep(10)
                    continue
            except KeyError, TypeError:
                pass

            # API limit reached. Recalculation of tagNameFormatted
            if res.status_code == 410 and res.json()["error"] == "PaginationExtension::PaginationError":
                last1000id = data[-1]["id"]
                params["tags"] = f"{tagname}+id:<{last1000id}"
                params["page"] = 1
                continue

            # Stops, if API responds with illegal shit
            if res.status_code != 200:
                logging.error("[DANBOORU] - Fetching gave illegal status code: %s . response: %s", res.status_code, res.text)
                raise cf.ExtractorExitError("Fetching gave illegal status code: %s . response: %s", res.status_code, res.text)

            data = res.json()
            for post in data:
                try:
                    post_data = await self._get_post_data(json_data=post)
                except KeyError:
                    logging.error("[DANBOORU] - Keyerror encountered on post %s ", post["id"])
                    continue
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            more_files = bool(data)
            truepage += 1
            params["page"] += 1
