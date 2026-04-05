"""Main module for interacting with https://hypnohub.net/ ."""

from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class NetworkError(Exception):
    """Raised, when code gets unexpected responses when talking to a server."""


@final
class HypnohubAPI(scraper.BooruScraper):
    HOMEPAGE = "https://hypnohub.net/index.php"
    API_URL = HOMEPAGE
    URL_TAG = "https://hypnohub.net/index.php?page=post&s=list&tags={tagname}"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?hypnohub\.net.*id=(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?hypnohub\.net/index\.php\?(?:.+)?tags=([^/&\?]+)"

    ME = "hypnohub"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = False

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds())

        async def setup_session() -> bool:
            params: dict[str, str | int] = {
                "q": "index",
                "page": "dapi",
                "json": 1,
            }
            self.session.params = params
            return True

        if not await setup_session():
            return False

        return True

    async def does_this_exist(self, tag_name: str) -> bool:
        params: dict[str, str | int] = {"s": "post", "limit": 100, "pid": 0, "tags": self.format_tagname(tag_name)}
        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params=params)
        return bool(res.text)

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post id nor json_data given (one is necessary).")
            params = {"s": "post", "id": post_id}
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)
            json_data = res.json()[0]
        if post_id is None:
            post_id = str(json_data["id"])

        tags = scraper.TagsData(
            tags=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tags"]).split(" ")],
        )

        download_url = json_data["file_url"]
        extension = f.match_extension(download_url)
        assert extension
        return scraper.PostData(
            identifier=post_id,
            filehash=str(json_data["hash"]),
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=tags,
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        more_files = True
        truepage = 0
        data: list[dict[str, str | int]] = []
        tagname = self.format_tagname(tagname)

        params: dict[str, str | int] = {"s": "post", "limit": 100, "pid": 0, "tags": tagname}
        assert isinstance(params["pid"], int)
        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)

            # API limit reached. Recalculation of tagNameFormatted
            if params["pid"] > 2000:
                last2000id = data[-1]["id"]
                params["pid"] = 0
                params["tags"] = f"{tagname}+id:<{last2000id}"
                continue

            # Empty json <=> no more files there
            if res.status_code == 200 and not res.json():
                return

            data = res.json()
            for post in data:
                if str(post["id"]) in update_ids:
                    return
                yield await self._get_post_data(json_data=post)

            more_files = bool(data)
            params["pid"] += 1
            truepage += 1
