"""Main module for interacting with https://www.rule34.xyz and https://www.rule34.world ."""

import logging
import re
from collections.abc import AsyncGenerator, Generator, Mapping
from typing import Any, final, override

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class _Rule34XyzWorldRoot(scraper.DownloadhistoryScraper):
    POST_PATTERN = r"(?:https?://)?(?:www\.)?rule34\.(?:xyz|world)/post/(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?rule34\.(?:xyz|world)/([^/&\?]+)"
    FILENAME_TO_ID_PATTERN = r"rule34(?:xyz|world)_(\d+)_"

    URL_TAG: str

    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(headers=self.headers)
        return True

    async def request(self, url: str, params: Mapping[str, str | int] | None = None) -> httpx.Response:
        await self.LIMIT.wait()
        res = await self.session.get(url, params=params)
        return res

    @override
    async def does_this_exist(self, tagname: str) -> bool:
        return True  # TODO(TheTimebreaker): implement this

    @override
    def is_content_rating_allowed(self, data: scraper.PostData) -> bool:
        return True  # website exposes nothing in that regard

    async def _get_post_data(
        self, post_id: str | None = None, _json_data: dict[str, Any] | None = None, post_url: str | None = None
    ) -> scraper.PostData:
        def _get_post_postid(post_url: str) -> str:
            post_id = re.match(self.POST_PATTERN, post_url)
            if not post_id:
                msg = f"Could not extract post ID from post URL: {post_url}"
                logging.error("[%s] - %s", self.ME.upper(), msg)
                raise cf.ExtractorSkipError(msg)
            return post_id.group(1)

        def _get_post_downloadelements(soup: bs4.BeautifulSoup) -> list[scraper.PostElement]:
            for element in soup.find_all("source", {"srcset": True}):
                element_src = element.get("srcset", None)
                if element_src and f"/{post_id}/" in element_src:
                    element_src = str(element_src)
                    extension = f.match_extension(element_src)
                    if not extension:
                        logging.error("[%s] - Could not extract file extension from %s", self.ME.upper(), post_url)
                        raise cf.ExtractorSkipError
                    return [scraper.PostElementLinks(download_url=element_src, extension=extension)]
            logging.error("[%s] - Could not extract download URL from %s", self.ME.upper(), post_url)
            raise cf.ExtractorSkipError

        def _get_post_tags(soup: bs4.BeautifulSoup) -> scraper.TagsData:  # TODO(TheTimebreaker): Show More button hides some tags
            tag_element = soup.find("app-tag-list")
            if not tag_element:
                raise
            _artists: list[str] = []
            _characters: list[str] = []
            _metatags: list[str] = []
            _parodies: list[str] = []
            _tags: list[str] = []
            for tag in tag_element.find_all("app-tag-chip"):
                tag_h4 = tag.find("h4")
                if not tag_h4:
                    raise
                tagname = str(tag_h4.contents[0])
                if tag.find("div", {"class": "chip--tag-artist"}):
                    _artists.append(tagname)
                elif tag.find("div", {"class": "chip--tag-character"}):
                    _characters.append(tagname)
                elif tag.find("div", {"class": "chip--tag-meta"}):
                    _metatags.append(tagname)
                elif tag.find("div", {"class": "chip--tag-copyright"}):
                    _parodies.append(tagname)
                elif tag.find("div", {"class": "chip--tag-general"}):
                    _tags.append(tagname)
            return scraper.TagsData(artists=_artists, characters=_characters, metatags=_metatags, parodies=_parodies, tags=_tags)

        if post_url is None:
            if post_id:
                post_url = post_id
            else:
                raise ValueError("Post url must be given, all other parameters are irrelevant.")

        res = await self.request(post_url)
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        post_id = _get_post_postid(post_url)
        elements = _get_post_downloadelements(soup)
        tags = _get_post_tags(soup)

        return scraper.PostData(
            identifier=post_id,
            elements=elements,
            tags=tags,
        )

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False  # noqa: ARG002
    ) -> AsyncGenerator[scraper.PostData]:
        def extract_posts_from_soup(soup: bs4.BeautifulSoup) -> Generator[str]:
            div = soup.find("div", {"class": "box-grid"})
            if not div:
                raise
            elements = div.find_all("a", {"class": "box"})
            for element in elements:
                href = element["href"]
                if not href:
                    raise
                yield f"{self.HOMEPAGE}{href}"

        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        api_url = self.URL_TAG.format(tagname=tagname)
        params = {"page": 1}
        if not isinstance(params["page"], int) or not isinstance(params["cursor"], str):
            raise ValueError

        while True:
            res = await self.request(api_url, params=params)
            soup = bs4.BeautifulSoup(res.text, "html.parser")

            # if not res.json()["data"]:  # type: ignore
            #     more_files = False
            #     return

            last_postid: str = ""
            posts = extract_posts_from_soup(soup)
            for post_url in posts:
                post_data = await self._get_post_data(post_url=post_url)
                identifier = post_data["identifier"]
                if str(identifier) in update_ids:
                    return

                yield post_data
                last_postid = identifier

            params["page"] += 1
            params["cursor"] = last_postid


@final
class Rule34XYZ(_Rule34XyzWorldRoot):
    HOMEPAGE = "https://rule34.xyz/"
    URL_TAG = "https://rule34.xyz/{tagname}"

    ME = "rule34xyz"
    WEBSITE_NAME = "rule34xyz"


@final
class Rule34World(_Rule34XyzWorldRoot):
    HOMEPAGE = "https://rule34.world/"
    URL_TAG = "https://rule34.world/{tagname}"

    ME = "rule34world"
    WEBSITE_NAME = "rule34world"
