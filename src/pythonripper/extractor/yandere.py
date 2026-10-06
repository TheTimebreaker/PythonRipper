"""Main module for interacting with https://yande.re/ ."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.model import YandereRatings


@final
class YandereAPI(scraper.DownloadhistoryScraper):
    HOMEPAGE = "https://yande.re"
    API_URL = "https://yande.re/post.json"
    URL_TAG = "https://yande.re/post?tags={tagname}"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?yande\.re/post/show/(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?yande\.re(?:.+)tags=([^/&\?]+)"

    ME = "yandere"
    WEBSITE_NAME = ME
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = False

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        return True

    def format_tagname(self, tagname: str) -> str:
        return tagname.replace(" ", "_")

    async def does_this_exist(self, tagname: str) -> bool:
        params: dict[str, int | str] = {"limit": 50, "page": 1, "tags": self.format_tagname(tagname)}
        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params=params)
        return bool(res.json())

    def create_ratings_searchtag(self, formatted_tagname: str) -> str:
        cfg = self.config.settings.extractor.yandere.allowed_ratings
        len_cfg = len(cfg)
        if len(set(YandereRatings)) != 3:
            raise NotImplementedError("YANDERE - Ratings set length is not 3!")

        if len_cfg == 0:
            msg = f"[{self.ME.upper()}] - Can't fetch posts, when none of the content ratings are enabled. Configure this in your settings!"
            logging.error(msg)
            raise cf.ExtractorStopError(msg)

        elif len_cfg == 1:
            return f"{formatted_tagname} rating:{next(iter(cfg))}"

        elif len_cfg == 2:  # We invert the set at 3 because less words in the search tag == lower risk of being timed out
            inverted_cfg = set(YandereRatings) - cfg
            return f"{formatted_tagname} -rating:{next(iter(inverted_cfg))}"

        elif len_cfg == 3:
            return formatted_tagname

        else:
            raise NotImplementedError

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")

            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params={"tags": f"id:{post_id}"})
            json_data = res.json()[0]

        download_url = json_data["file_url"]
        assert isinstance(download_url, str)
        extension = f.match_extension(download_url)
        if not extension:
            msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
            logging.error(msg)
            raise cf.ExtractorSkipError(msg) from AttributeError
        return scraper.PostData(
            identifier=json_data["id"],
            filehash=json_data["md5"],
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=scraper.TagsData(
                tags=[self.invert_formatting(tag) for tag in str(json_data["tags"]).split(" ")],
            ),
        )

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        more_files = True
        tagname = self.format_tagname(tagname)
        if ignore_contentfilters is False:
            tagname = self.create_ratings_searchtag(tagname)

        params: dict[str, int | str] = {"limit": 50, "page": 1, "tags": tagname}
        assert isinstance(params["page"], int)
        data: list[dict[Any, Any]] = []
        while more_files:
            if params["page"] > 100:
                last100id = data[-1]["id"]
                params["page"] = 1
                params["tags"] = f"{tagname} id:<{last100id}"
                continue

            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)

            if res.status_code != 200:
                logging.error("[%s] - Request status code %s :(", self.ME.upper(), res.status_code)
                raise cf.ExtractorExitError("Request status code %s :(", res.status_code)

            data = res.json()
            logging.info("[%s] - data %s", self.ME.upper(), data)
            for post in data:
                post_data = await self._get_post_data(json_data=post)
                if str(post_data["identifier"]) in update_ids:
                    return
                logging.info("[%s] - post data %s", self.ME.upper(), post_data)
                yield post_data

            more_files = bool(data)
            params["page"] += 1
