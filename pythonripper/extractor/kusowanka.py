"""Main module for interacting with https://kusowanka.com/ ."""

import logging
import re
import sqlite3
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class SqlTagIDs:
    def __init__(self) -> None:
        self.path = cfg.c._downloadhistory_path() / "kusowanka_tagids.db"
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS tags (tagid INTEGER PRIMARY KEY, tagname TEXT NOT NULL)""")
        self.conn.commit()

    def get(self, tagid: int) -> str:
        """Main interfacing function that returns the tagname of a given tag ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT tagname FROM tags WHERE tagid = ?", (tagid,))
        row = cursor.fetchone()
        if row is not None:
            return str(row[0])
        raise AttributeError(f"No tag found for tagid {tagid}")

    def add(self, tagname: str, tagid: int) -> None:
        """Adds tagid to data."""
        tagname = repr(tagname)
        while tagname.startswith(("'", '"')):
            tagname = tagname[1:]
        while tagname.endswith(("'", '"')):
            tagname = tagname[:-1]
        self.conn.execute(
            "INSERT OR IGNORE INTO tags (tagid, tagname) VALUES (?, ?)",
            (tagid, tagname),
        )
        self.conn.commit()


@final
class KusowankaAPI(scraper.BooruScraper):
    """Front facing API class for kusowanka"""

    HOMEPAGE = "https://kusowanka.com/"
    URL_BASE = HOMEPAGE
    URL_TAG = (
        "https://kusowanka.com/artist/{tagname}",
        "https://kusowanka.com/character/{tagname}",
        "https://kusowanka.com/metadata/{tagname}",
        "https://kusowanka.com/parody/{tagname}",
        "https://kusowanka.com/tag/{tagname}",
    )

    POST_PATTERN = r"(?:https?://)?(?:www\.)?kusowanka\.com/post/(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?kusowanka\.com/((?:artist|character|metadata|parody|tag)/[^/&\?]+)"

    ME = "kusowanka"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "-"
    IS_GOOGLE_SEARCHABLE = False

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.tagids = SqlTagIDs()
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        return True

    def format_tagname(self, tagname: str) -> str:
        tagname = (
            tagname.replace(" ", "-").replace(":", "-").replace("(", "").replace(")", "").replace(";", "-").replace(".", "-").replace("?", "-")
        ).replace("--", "-")
        while tagname.startswith("-"):
            tagname = tagname[1:]
        while tagname.endswith("-"):
            tagname = tagname[:-1]
        return tagname

    async def does_this_exist(self, tagname: str) -> bool:
        api_url = f"{self.URL_BASE}/{self.format_tagname(tagname)}/?page=1"
        await self.LIMIT.wait()
        res = await self.session.head(api_url)
        return res.status_code == 200

    async def _get_post_data(
        self, post_id: str | None = None, _json_data: dict[str, Any] | None = None, soup: bs4.BeautifulSoup | None = None
    ) -> scraper.PostData:
        async def _get_post_data_from_postpage(soup: bs4.BeautifulSoup) -> scraper.PostData:
            async def get_tag_list(soup: bs4.BeautifulSoup, main_class: str) -> list[str]:
                results: list[str] = []
                elements = soup.find("ul", {"class": main_class})
                if elements:
                    for element in elements.find_all("li"):
                        assert isinstance(element, bs4.Tag)
                        tmp_results = element.find("a", {"href": True}).contents[0]  # type: ignore
                        tagname = str(tmp_results)
                        results.append(tagname)

                        tagid = int(element.find("button", {"class": "remove", "data_id": True})["data_id"])  # type: ignore
                        self.tagids.add(tagname=tagname, tagid=tagid)
                return results

            async def get_parodies(soup: bs4.BeautifulSoup) -> list[str]:
                return await get_tag_list(soup, "parodies_list")

            async def get_characters(soup: bs4.BeautifulSoup) -> list[str]:
                return await get_tag_list(soup, "characters_list")

            async def get_artists(soup: bs4.BeautifulSoup) -> list[str]:
                return await get_tag_list(soup, "artists_list")

            async def get_metatags(soup: bs4.BeautifulSoup) -> list[str]:
                return await get_tag_list(soup, "metadatas_list")

            async def get_tags(soup: bs4.BeautifulSoup) -> list[str]:
                return await get_tag_list(soup, "tags_list")

            async def get_post_id(soup: bs4.BeautifulSoup) -> str:
                title_tag = soup.find("title")
                assert title_tag
                title = re.match(r"Post (\d+) - Hentai", str(title_tag.contents[0]))
                assert title
                return title.group(1)

            async def get_download_url(soup: bs4.BeautifulSoup) -> str:
                try:
                    imglink = str(soup.find("div", {"class": "preview_image"}).find("img", {"data-src": True})["data-src"])  # type: ignore
                except AttributeError:
                    return soup.find("video").find("source")["src"]  # type: ignore
                pattern = (
                    r"https://(?:.+)kusowanka\.com/(?:samples|original|thumb)/"
                    r"([a-z\d]{32}"
                    r"/[a-z\d]{32}"
                    r"/[a-z\d]{32}"
                    r"/[a-z\d]{32}"
                    r"/[a-z\d]{32}"
                    ")"
                    r"\.[a-z]{2,5}"
                )
                matched = re.match(pattern, imglink)
                assert matched
                imglink = imglink.replace("/samples/", "/original/").replace("/thumb/", "/original/")

                old_extension = f.match_extension(imglink)
                try:
                    new_extension = str(soup.find("div", {"class": "p_btns"}).find("button", {"class": "expand"})["data-type"])  # type: ignore
                except TypeError, AttributeError:  # no button there -> extension is retained OR login required
                    if not all(x in str(soup) for x in ("You must", "login", "or", "register", "to view this content")):
                        assert old_extension
                        new_extension = old_extension
                    else:
                        for extension in ("jpg", "png", "jpeg", "bmp", "gif", "mp4"):
                            testlink = imglink.replace(f".{old_extension}", f".{extension}")
                            await self.LIMIT.wait()
                            res = await self.session.head(testlink, timeout=60)
                            if res.status_code == 200:
                                new_extension = extension
                                logging.info("[%s] - Download file extension found as %s .", self.ME.upper(), new_extension)
                                break
                        else:
                            raise TypeError(
                                f"Could not determine filetype of original file / post id: {post_id}."
                            )  # pylint:disable=raise-missing-from

                if old_extension is None:
                    raise TypeError("Variable was unexpectedly empty.")
                imglink = imglink.replace(old_extension, new_extension)

                return str(imglink)

            post_id = await get_post_id(soup)
            logging.info("[%s] - Getting data for post %s", self.ME.upper(), post_id)

            download_url = await get_download_url(soup)
            extension = f.match_extension(download_url)
            if not extension:
                msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
                logging.error(msg)
                raise cf.ExtractorSkipError(msg) from AttributeError

            tags = scraper.TagsData(
                artists=await get_artists(soup),
                characters=await get_characters(soup),
                parodies=await get_parodies(soup),
                metatags=await get_metatags(soup),
                tags=await get_tags(soup),
            )

            results = scraper.PostData(
                identifier=post_id,
                elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
                tags=tags,
            )
            return results

        async def _get_post_id_from_lister_soup(post_soup: bs4.BeautifulSoup) -> str:
            a_tag = post_soup.find("a", {"href": True})
            assert a_tag
            post_ref = a_tag["href"]
            assert isinstance(post_ref, str)
            post_id_matched = re.match(r"/post/(\d+)", post_ref)
            assert post_id_matched
            post_id = post_id_matched.group(1)
            assert isinstance(post_id, str)
            return post_id

        async def _get_post_soup(post_id: str) -> bs4.BeautifulSoup:
            await self.LIMIT.wait()
            res = await self.session.get(f"""{self.URL_BASE}/post/{post_id}/""")
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            return soup

        if soup is None:
            if post_id is None:
                raise ValueError("Neither post_id nor soup object given (one is necessary).")
            soup = await _get_post_soup(post_id)

        try:
            return await _get_post_data_from_postpage(soup)
        except AssertionError:
            if post_id is None:
                post_id = await _get_post_id_from_lister_soup(soup)
            soup = await _get_post_soup(post_id)
            return await _get_post_data_from_postpage(soup)

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        data: dict[str, str]
        tagname = self.format_tagname(tagname)
        page = 1
        while True:
            api_url = f"""{self.URL_BASE}/{tagname}/?page={page}"""
            await self.LIMIT.wait()
            res = await self.session.get(api_url)

            soup = bs4.BeautifulSoup(res.text, "html.parser")
            data = soup.find("div", {"class": "box_thumbs"})  # type: ignore
            assert isinstance(data, bs4.Tag)
            posts = data.find_all("div", {"class": "box_thumb"})

            if len(posts) == 0:
                return

            for post in posts:
                post_data = await self._get_post_data(soup=post)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            page += 1
