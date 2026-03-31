"""Main module for interacting with https://tangs.gallery/ ."""

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import bs4
import httpx
import xmltodict

import pythonripper.extractor.toolbox.centralfunctions as cf
import pythonripper.extractor.toolbox.files as f
import pythonripper.extractor.toolbox.scraperclasses as scraper


@final
class TangsGalleryAPI(scraper.ArtistWebsiteScraper):
    BASE_URL = "https://tangs.gallery"

    ME = "tangsgallery"
    LIMIT = asynciolimiter.Limiter(10)
    SPACE_REPLACE = " "

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), follow_redirects=True)

        async def start_session() -> bool:
            res = await self.session.get("https://tangs.gallery/art")  # general page to initialize cookies and stuff

            soup = bs4.BeautifulSoup(res.text, "html.parser")  # Creates Soup element and fetches the things we need for the form post.
            post_consent = soup.find("input", {"name": "give_consent"})["value"]  # type: ignore
            post_redirect = soup.find("input", {"name": "redirect_to"})["value"]  # type: ignore
            post_token = soup.find("input", {"name": "_token"})["value"]  # type: ignore

            # Cannot use if any() call here because mypy is too stupid for that : ^)
            if not isinstance(post_consent, str) or not isinstance(post_redirect, str) or not isinstance(post_token, str):
                logging.error("[TANGSGALLERY] - Some HTML extracted values were incorrect.")
                raise ValueError("Some HTML extracted values were incorrect.")

            res = await self.session.post(
                "https://tangs.gallery/enter?redirect=art", data={"give_consent": post_consent, "redirect_to": post_redirect, "_token": post_token}
            )
            if res.status_code == 200:
                return True
            return False

        if not await start_session():
            return False

        return True

    async def _get_post_data(
        self, post_id: str | None = None, _json_data: dict[str, Any] | None = None, post_soup: bs4.Tag | None = None
    ) -> scraper.PostData:
        if post_id is None or post_soup is None:
            raise ValueError("Both post ID and post soup must be given.")

        download_url = str(post_soup["enclosure"]["@url"]).replace("thumbnails/", "")  # type: ignore
        extension = f.match_extension(download_url)
        assert extension

        return scraper.PostData(identifier=post_id, elements=scraper.PostElementLinks(download_url=download_url, extension=extension))

    async def _fetch_posts(self, _tagname: Any = None, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        res = await self.session.get("https://tangs.gallery/rss.xml")
        res_xml = xmltodict.parse(res.text)
        items = res_xml["rss"]["channel"]["item"]

        for item in items:
            matched_id = re.match(r".+/posts/(.+)", item["link"])
            assert matched_id
            post_id = str(matched_id.group(1))
            post_data = await self._get_post_data(post_id=post_id, post_soup=item)
            if post_id in update_ids:
                return
            yield post_data
