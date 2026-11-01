"""Main module for interacting with https://www.eroprofile.com/ ."""

import logging
import re
from collections.abc import AsyncGenerator, Generator
from itertools import combinations, count
from typing import Any, Literal, final

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


def combinations_preserving_order(items: list[str]) -> Generator[list[str]]:
    yield from [list(combo) for r in range(1, len(items) + 1) for combo in combinations(items, r)]


class EroProfile(scraper.TaggableScraper):
    HOMEPAGE = "https://reddit.com"
    POST_PATTERN = r"/m/(?:photos|videos)/view/([a-zA-Z\d\-]+)"

    URL_TAG = "https://www.eroprofile.com/m/{endpoint}/search"
    URL_POST = "https://www.eroprofile.com/m/{endpoint}/view/{post_id}"

    ME = "eroprofile"
    WEBSITE_NAME = "eroprofile"
    LIMIT = asynciolimiter.LeakyBucketLimiter(100 / 60, capacity=990)
    SPACE_REPLACE = "-"
    PAGE_START: int = 1

    session: httpx.AsyncClient
    mode: Literal["photos", "videos"]

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds())
        return True

    async def request(self, url: str, params: dict[str, str | int] | None = None) -> httpx.Response:
        await self.LIMIT.wait()
        res = await self.session.get(url, params=params)
        return res

    def format_tagname(self, tagname: str) -> str:
        remove_what_set = {" ", "/", "(", ")", "-"}
        for what in remove_what_set:
            tagname = tagname.replace(what, "")
        return tagname.lower()

    async def _get_post_data(self, post_id: str | None = None, _json_data: dict[str, Any] | None = None) -> scraper.PostData:
        def _get_download_elements(post_soup: bs4.BeautifulSoup) -> scraper.PostElementDownloadLinks:
            try:
                if self.mode == "photos":
                    container = post_soup.find("div", {"class": "photo-container"})
                    img_tag = container.find("img")  # type: ignore
                    source_url = img_tag["src"]  # type: ignore
                    extension = f.match_extension(source_url)  # type: ignore
                elif self.mode == "videos":
                    container = post_soup.find("div", {"class": "video-container"})
                    video_tag = container.find("video")  # type: ignore
                    source_tag = video_tag.find("source")  # type: ignore
                    source_url = source_tag["src"]  # type: ignore
                    extension = f.match_extension(source_url)  # type: ignore
                if not isinstance(source_url, str):
                    raise ValueError
                if not extension:
                    raise ValueError
                return scraper.PostElementDownloadLinks(download_url=source_url, extension=extension)
            except (KeyError, ValueError) as error:
                raise cf.ExtractorSkipError from error

        if post_id is None:
            raise ValueError("No post id given. Other fetching methods are impossible.")
        post_url = self.URL_POST.format(endpoint=self.mode, post_id=post_id)
        res = await self.session.get(post_url)

        post_soup = bs4.BeautifulSoup(res.text, "html.parser")

        return scraper.PostData(
            identifier=post_id,
            title=self.invert_formatting(post_id),
            elements=_get_download_elements(post_soup),
        )

    async def does_this_exist(self, tagname: str) -> bool:
        try:
            self.__map_tag_to_niche(tagname)
            return True
        except NotImplementedError:
            return False

    def __map_tag_to_niche(self, tagname: str) -> str | int:
        tagname = self.format_tagname(tagname)
        match tagname:
            case "all":
                return "all"
            case "allsf" | "allnonextreme":
                return "all-sf"
            case "amateurmomsmature" | "amateurmom" | "amateurmoms" | "amateurmature":
                return 13
            case "amateurteens" | "amateurteen" | "teen" | "teens":
                return 14
            case "amateurs" | "amateur":
                return 12
            case "asian":
                return 19
            case "ass":
                return 27
            case "bdsm":
                return 25
            case "bigladies":
                return 5
            case "bigtits" | "bigtit":
                return 11
            case "bisexual":
                return 18
            case "blackebony" | "black" | "ebony":
                return 20
            case "celeb":
                return 23
            case "dogging":
                return 33
            case "extreme" | "perverse" | "pervert" | "bizarre" | "extremeperversebizarre" | "extremeperverse" | "extremebizarre" | "perversebizarre":
                return 1
            case "facialcum" | "facial" | "cum":
                return 24
            case "fetishkinky" | "fetish" | "kinky":
                return 10
            case "fuckingsucking" | "fucking" | "sucking":
                return 26
            case "fun":
                return 17
            case "gay":
                return 3
            case "gaybizarre" | "gayextreme" | "gaybizarregayextreme" | "gaybizareextreme":
                return 2
            case "hairy":
                return 7
            case "interracial":
                return 15
            case "lesbian":
                return 6
            case "lingerie" | "panties" | "lingeriepanties":
                return 30
            case "male":
                return 4
            case "malescat":
                return 31
            case "nudist" | "voyeur" | "public" | "nudistvoyeur" | "nudistpublic" | "nudistvoyeurpublic" | "voyeurpublic":
                return 16
            case "other" | "cartoon" | "fake" | "othercartoon" | "otherfake" | "cartoonfake" | "othercartoonfake":
                return 28
            case "pissing":
                return 22
            case "pregnant":
                return 32
            case "scat":
                return 29
            case (
                "shemale"
                | "ts"
                | "tv"
                | "shemalets"
                | "shemaletv"
                | "tstv"
                | "shemaletstv"
                | "trans"
                | "transsexual"
                | "transexual"
                | "transgender"
                | "transvestite"
            ):
                return 9
            case "squirting":
                return 34
            case "swingers" | "gangbang" | "swingersgangbang" | "swinger" | "swingergangbang":
                return 8
            case "tribute":
                return 21
            case "vintage":
                return 35

        raise NotImplementedError

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False  # noqa: ARG002
    ) -> AsyncGenerator[scraper.PostData]:
        def post_selector(tag: bs4.element.Tag) -> bool:
            def picture_selector(tag: bs4.element.Tag) -> bool:
                return tag.name == "div" and tag.has_attr("class") and "grid-tile-photo" in str(tag.get("class"))

            def video_selector(tag: bs4.element.Tag) -> bool:
                return tag.name == "div" and tag.has_attr("class") and "grid-tile-video" in str(tag.get("class"))

            return picture_selector(tag) or video_selector(tag)

        def extract_postid_from_element(element: bs4.Tag) -> str:
            element_href = element.find("a", {"class": "preview", "href": True})
            if not element_href:
                raise ValueError
            href = str(element_href["href"])
            matched = re.match(self.POST_PATTERN, href)
            if not matched:
                raise cf.ExtractorStopError
            post_id = str(matched.group(1))
            return post_id

        if update_ids is None:
            update_ids = []

        niche = self.__map_tag_to_niche(tagname)
        url = self.URL_TAG.format(endpoint=self.mode)

        for page in count(self.PAGE_START):
            params: dict[str, str | int] = {
                "niche": niche,
                "pnum": page,
            }

            res = await self.request(url, params=params)
            if res.status_code == 404:
                return

            soup = bs4.BeautifulSoup(res.text, "html.parser")

            elements = soup.find_all(post_selector)
            if not elements:
                return

            for element in elements:
                post_id = extract_postid_from_element(element)
                if post_id in update_ids:
                    return
                try:
                    yield await self._get_post_data(post_id)
                except cf.ExtractorSkipError:
                    logging.error("[%s] - Failed to fetch post data for post_id %s", self.ME.upper(), post_id)


@final
class EroProfilePictures(EroProfile):
    mode = "photos"
    ME = "eroprofile-photos"


@final
class EroProfileVideos(EroProfile):
    mode = "videos"
    ME = "eroprofile-videos"
