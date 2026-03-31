"""Main module for interacting with https://rule34.us/ ."""

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
class Rule34usAPI(scraper.BooruScraper):
    API_URL = "https://rule34.us/index.php"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?rule34\.us.*id=(\d+)"

    ME = "rule34us"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.download_headers = {"Referer": "https://rule34.us/index.php"}
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        return True

    async def does_this_exist(self, tagname: str) -> bool:
        params: dict[str, str | int] = {"r": "posts/index", "q": self.format_tagname(tagname)}
        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params=params)
        return "No results found for this search query" not in res.text

    async def _get_post_data(self, post_id: str | None = None, _json_data: Any = None, post_soup: bs4.Tag | None = None) -> scraper.PostData:
        if post_soup:
            post_id = str(post_soup.a["id"])  # type: ignore
        elif post_id is None:
            raise TypeError("Neither post_id nor post_soup given (one is necessary).")

        url = f"""{self.API_URL}?r=posts/view&id={post_id}"""
        await self.LIMIT.wait()
        res = await self.session.get(url)
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        tags_soup = {
            "artists": soup.find("ul", {"class": "tag-list-left"}).find_all("li", {"class": "artist-tag"}),  # type: ignore
            "characters": soup.find("ul", {"class": "tag-list-left"}).find_all("li", {"class": "character-tag"}),  # type: ignore
            "parodies": soup.find("ul", {"class": "tag-list-left"}).find_all("li", {"class": "copyright-tag"}),  # type: ignore
            "metadata": soup.find("ul", {"class": "tag-list-left"}).find_all("li", {"class": "metadata-tag"}),  # type: ignore
            "tags": soup.find("ul", {"class": "tag-list-left"}).find_all("li", {"class": "general-tag"}),  # type: ignore
        }
        tags_list: dict[str, list[str]] = {}
        for tagtype, tags in tags_soup.items():
            tags_list[tagtype] = []
            for tag in tags:
                tagfind = tag.find("a")
                if tagfind and tagfind["href"] and "http" in tagfind["href"]:
                    tags_list[tagtype].append(str(tagfind.contents[0]))
        tags_data = scraper.TagsData(
            artists=tags_list["artists"],
            characters=tags_list["characters"],
            parodies=tags_list["parodies"],
            metatags=tags_list["metadata"],
            tags=tags_list["tags"],
        )

        download_soup = soup.find("ul", {"class": "tag-list-left"}).find_all("li", {"class": "character-tag"})  # type: ignore
        for charactertag in download_soup:
            if charactertag.contents[0] == "Original":
                download_url = str(charactertag.parent["href"])  # type: ignore
                extension = f.match_extension(download_url)
                assert extension
                break
        else:
            logging.error("[RULE34US] - Could not extract download link from post %s ", post_id)
            raise cf.ExtractorExitError("[RULE34US] - Could not extract download link from post %s ", post_id)

        filehash = download_url.split("/")[-1].split(".")[0]

        return scraper.PostData(
            identifier=post_id,
            filehash=filehash,
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=tags_data,
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)

        more_files = True
        params: dict[str, str | int] = {"r": "posts/index", "q": tagname, "page": 0}
        assert isinstance(params["page"], int)
        last_element: scraper.PostData | None = None

        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)

            # pagination limit reached. Recalculation of tagname parameter
            if "This browsing action would use up too much CPU" in res.text:
                assert last_element
                last_id = last_element["identifier"]
                params["page"] = 0
                params["q"] = f"{tagname}+id:<{last_id}"
                continue

            soup = bs4.BeautifulSoup(res.text, "html.parser")
            images = soup.find("div", {"class": "thumbail-container"}).find_all("div")  # type: ignore
            for post in images:
                post_data = await self._get_post_data(post_soup=post)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            last_element = post_data

            more_files = bool(images)
            params["page"] += 1
