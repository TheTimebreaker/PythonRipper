"""Main module for interacting with https://www.akairiot.com/ ."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class AkaiRiot(scraper.ArtistWebsiteScraper):
    BASE_URL = "https://www.akairiot.com/"

    ME = "akairiot"
    LIMIT = asynciolimiter.Limiter(10)
    SPACE_REPLACE = " "

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), follow_redirects=True)
        return True

    async def _get_post_data(
        self, _post_id: str | None = None, _json_data: dict[str, Any] | None = None, post_soup: bs4.Tag | None = None
    ) -> scraper.PostData:
        if post_soup is None:
            raise ValueError("Giving post soup required!")

        post_id = str(post_soup["data-slide-id"])
        tmp = post_soup.find("img")
        if not tmp:
            msg = f"[{self.ME.upper()}] - Img tag not found for post {post_id} ."
            logging.error(msg)
            raise cf.ExtractorSkipError(msg) from AttributeError
        download_url = str(tmp["data-src"])
        extension = f.match_extension(download_url)
        if not extension:
            msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
            logging.error(msg)
            raise cf.ExtractorSkipError(msg) from AttributeError
        return scraper.PostData(identifier=post_id, elements=scraper.PostElementLinks(download_url=download_url, extension=extension))

    async def _fetch_posts(self, _tagname: Any = None, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        res = await self.session.get(self.BASE_URL)
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        tmp = soup.find("div", {"id": "thumbList"})
        if not tmp:
            msg = f"[{self.ME.upper()}] - Could not find thumbList element ."
            logging.error(msg)
            raise cf.ExtractorStopError(msg) from AttributeError
        items = tmp.find_all("span")

        for item in items:
            post_data = await self._get_post_data(post_soup=item)
            if post_data["identifier"] in update_ids:
                return
            yield post_data
