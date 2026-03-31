"""Main module for interacting with https://sss.booru.org/ ."""

from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class SuperSatanSonAPI(scraper.ArtistWebsiteScraper):
    API_URL = "https://sss.booru.org/index.php"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?sss\.booru\.org.*id=(\d+)"

    ME = "supersatanson"
    LIMIT = asynciolimiter.Limiter(2)
    SPACE_REPLACE = "_"

    async def init(self) -> bool:
        self.params = {"page": "post"}
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), params=self.params, headers=self.headers)
        return True

    async def _get_post_data(self, post_id: str | None = None, _json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if post_id is None:
            raise ValueError("Post ID must be given.")

        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params={"s": "view", "id": post_id})
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        tmp = soup.find("img", {"id": "image"})
        assert tmp
        tmp2 = tmp["src"]
        assert isinstance(tmp2, str)

        download_url = str(tmp2)
        extension = f.match_extension(download_url)
        assert extension

        return scraper.PostData(identifier=post_id, elements=scraper.PostElementLinks(download_url=download_url, extension=extension))

    async def _fetch_posts(self, _tagname: Any = None, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        async def _latest_post_id() -> int:
            params_latest_post_id = {"s": "list", "tags": "all"}
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params_latest_post_id)
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            image_id = int(str(soup.find("span", {"class": "thumb"}).find("a")["id"][1:]))  # type: ignore #first letter is p for some reason
            return image_id

        if update_ids is None:
            update_ids = []

        for post_id_int in range(await _latest_post_id(), 0, -1):
            post_id = str(post_id_int)
            post_data = await self._get_post_data(post_id=post_id)
            if post_id in update_ids:
                return

            yield post_data
