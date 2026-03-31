"""Main module for interacting with https://rule34.paheal.net/ ."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper


@final
class Rule34pahealAPI(scraper.BooruScraper):
    API_URL = "https://rule34.paheal.net"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?rule34\.paheal\.net/post/view/(\d+)"

    ME = "rule34paheal"
    LIMIT = asynciolimiter.Limiter(1)
    SPACE_REPLACE = "_"

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        return True

    def format_tagname(self, tagname: str) -> str:
        tagname = tagname.lower()
        tagname = tagname.replace(" ", "_").replace("/", r"%2F")
        return tagname

    async def does_this_exist(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(f"""{self.API_URL}/post/list/{self.format_tagname(tagname)}""")
        return res.status_code == 200

    async def __get_post_data_listerhtml(self, soup: bs4.Tag) -> scraper.PostData:
        post_id = soup["data-post-id"]
        assert isinstance(post_id, str)
        tags = scraper.TagsData(tags=[x.replace(self.SPACE_REPLACE, " ") for x in str(soup["data-tags"]).split(" ")])
        download_url = str(soup.find("a", {"class": None})["href"])  # type: ignore
        extension = str(soup["data-ext"])
        assert isinstance(extension, str)
        md5 = download_url.split("/")[-1]
        return scraper.PostData(
            identifier=post_id, filehash=md5, tags=tags, elements=scraper.PostElementLinks(download_url=download_url, extension=extension)
        )

    async def __get_post_data_single(self, post_id: str) -> scraper.PostData:
        url = f"""{self.API_URL}/post/view/{post_id}"""
        await self.LIMIT.wait()
        res = await self.session.get(url)
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        tags_soup = soup.find("table", {"class": "tag_list"}).find("tbody").find_all("a", {"class": "tag_name"})  # type: ignore
        tags = []
        for tag in tags_soup:
            if tag["href"]:
                tags.append(str(tag.contents[0]).lower())

        try:
            download_soup = soup.find("section", {"id": "Imagemain"}).find("img", {"id": "main_image"})  # type: ignore
            download_url = str(download_soup["src"])  # type: ignore
            extension = str(download_soup["data-mime"]).replace("image/", "")  # type: ignore

        # NoneType => video
        except AttributeError:
            download_soup = soup.find("section", {"id": "Videomain"}).find("video", {"id": "main_image"}).find("source")  # type: ignore
            download_url = str(download_soup["src"])  # type: ignore
            extension = str(download_soup["type"]).replace("video/", "")  # type: ignore

        filehash = download_url.split("/")[-1]

        return scraper.PostData(
            identifier=post_id,
            filehash=filehash,
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=scraper.TagsData(tags=tags),
        )

    async def _get_post_data(self, post_id: str | None = None, _json_data: Any = None, post_soup: bs4.Tag | None = None) -> scraper.PostData:
        if post_soup:
            return await self.__get_post_data_listerhtml(post_soup)
        if not post_id:
            raise TypeError("Neither post_id nor post_soup given (one is necessary).")

        return await self.__get_post_data_single(post_id)

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        tagname_with_optional_id = tagname

        more_files = True
        page = 1
        last_element: scraper.PostData | None = None

        while more_files:
            api_url = f"""{self.API_URL}/post/list/{tagname_with_optional_id}/{page}"""
            await self.LIMIT.wait()
            res = await self.session.get(api_url)

            # rate limit
            if "Too Many Requests" in res.text or res.status_code == 429:
                await asyncio.sleep(10)
                continue

            # API limit reached. Recalculation of tagNameFormatted
            if page > 500:
                assert last_element
                last500id = last_element["identifier"]
                page = 1
                tagname_with_optional_id = f"{tagname}%20id:<{last500id}"
                continue

            # Paginated past last page
            if (
                "No images were found to match the search criteria. "
                "Try looking up a character/series/artist by another name if they go by more than one. "
                "Remember to use underscores in place of spaces and not to use commas. "
                "If you came to this page by following a link, try using the search box directly instead. See the FAQ for more information."
                in res.text
            ):
                return

            soup = bs4.BeautifulSoup(res.text, "html.parser")
            image_list = soup.find("section", {"id": "image-list"})
            assert image_list
            shm = image_list.find("div", {"class": "shm-image-list"})
            assert shm
            posts = shm.find_all("div", {"class": "shm-thumb"})
            assert posts

            for post in posts:
                post_data = await self._get_post_data(post_soup=post)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data
            last_element = post_data

            page += 1
