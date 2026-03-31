"""Main module for interacting with https://shellvi.carrd.co/ ."""

import re
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class ShellViAPI(scraper.ArtistWebsiteScraper):
    ME = "shellvi"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = " "

    async def init(self) -> bool:
        self.base_url = "https://shellvi.carrd.co"
        self.gallery_url = f"{self.base_url}/#gallery"
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds())
        return True

    async def _get_post_data(
        self, _post_id: str | None = None, _json_data: dict[str, Any] | None = None, post_soup: bs4.Tag | None = None
    ) -> scraper.PostData:
        if post_soup is None:
            raise ValueError("post_soup must be given.")
        download_url = f"{self.base_url}/{post_soup['href']}"
        tmp = re.match(r"assets/images/gallery[\w\d]{0,3}/([\w\d]+)_original", str(post_soup["href"]))
        assert tmp
        image_id = tmp.group(1)
        assert isinstance(image_id, str)

        extension = f.match_extension(download_url)
        assert extension
        return scraper.PostData(identifier=image_id, elements=scraper.PostElementLinks(download_url=download_url, extension=extension))

    async def _fetch_posts(self, _tagname: Any = None, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        res = await self.session.get(self.gallery_url)

        soup = bs4.BeautifulSoup(res.text, "html.parser")
        images = soup.find("section", {"id": "gallery-section"}).find_all("a", {"class": "thumbnail"})  # type: ignore

        for image in images:
            post_data = await self._get_post_data(post_soup=image)
            if post_data["identifier"] in update_ids:
                return
            yield post_data
