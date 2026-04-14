"""Main module for interacting with https://kemono.cr/ ."""

import json
import logging
from abc import abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class KemonoBase(scraper.TaggableScraper):
    HOMEPAGE = "https://kemono.cr"
    ARTIST_URL = f"{HOMEPAGE}/{"{service}"}/user/{"{username}"}"

    API_URL_BASE = f"{HOMEPAGE}/api/v1"
    API_ARTIST_URL = f"{API_URL_BASE}/{"{service}"}/{"{type}"}/{"{username}"}"
    API_ARTIST_URL_POSTS = f"{API_ARTIST_URL}/posts"
    API_ARTIST_URL_PROFILE = f"{API_ARTIST_URL}/profile"

    API_POST_URL = f"{API_ARTIST_URL}/post/{"{post_id}"}"

    DIRECT_URL = f"{HOMEPAGE}/data{"{path}"}"

    POST_PATTERN = (
        r"(?:https?://)?(?:www\.)?kemono\.cr/(afdian|patreon|fanbox|discord|fantia|boosty|gumroad|subscribestar|dlsite)/(user|server)/([^/?=]+)"
    )
    TAG_PATTERN = POST_PATTERN + r"/post/([^/?=])"

    ME = "kemono"
    LIMIT = asynciolimiter.LeakyBucketLimiter(2, capacity=100)
    SPACE_REPLACE = ""
    IS_GOOGLE_SEARCHABLE = False

    session: httpx.AsyncClient

    @property
    @abstractmethod
    def service(self) -> str: ...

    @property
    @abstractmethod
    def type(self) -> str: ...

    async def init(self) -> bool:
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/css",
        }
        self.download_headers = self.headers.copy()
        self.download_headers["Referer"] = "https://kemono.cr/"
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        return True

    async def does_this_exist(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(self.API_ARTIST_URL_PROFILE.format(service=self.service, type=self.type, username=self.format_tagname(tagname)))
        print(res.status_code)
        return res.status_code == 200

    async def resolve_tagnames_to_id(self, tagname: str) -> str:
        await self.LIMIT.wait()
        res = await self.session.get(self.API_ARTIST_URL_PROFILE.format(service=self.service, type=self.type, username=self.format_tagname(tagname)))
        if res.status_code == 200:
            ide = res.json().get("id")
            if ide:
                return str(ide)
        msg = f"[{self.ME.upper()}] - Could not resolve tagname {tagname} ."
        logging.error(msg)
        raise cf.ExtractorSkipError(msg)

    async def _get_post_data(
        self, post_id: str | None = None, json_data: dict[str, Any] | None = None, tagname: str | None = None
    ) -> scraper.PostData:
        if json_data is not None:
            raise ValueError("Reusing jsondata not supported.")

        if post_id is None or tagname is None:
            raise ValueError("Neither post id + tagname (service/user/user ID) nor json_data given (one is necessary).")

        tagname = self.format_tagname(tagname)
        await self.LIMIT.wait()
        res = await self.session.get(self.API_POST_URL.format(service=self.service, type=self.type, username=tagname, post_id=post_id))
        json_data = res.json()["post"]

        elements: list[scraper.PostElement] = []
        checked = set()
        attachments = [json_data.get("file", {}), *json_data.get("attachments", [])]
        for attachment in attachments:
            if not attachment:
                continue

            url = self.DIRECT_URL.format(path=attachment["path"])
            if url in checked:
                continue
            extension = f.match_extension(url)
            if extension is None:
                logging.error("[%s] - Post %s had a direct url (%s) with no valid extension .", self.ME.upper(), post_id, url)
                raise cf.ExtractorSkipError(
                    "[%s] - Post %s had a direct url (%s) with no valid extension .", self.ME.upper(), post_id, url
                ) from AttributeError

            elements.append(
                scraper.PostElementLinks(
                    download_url=url,
                    extension=extension,
                )
            )
            checked.add(url)

        result = scraper.PostData(
            source=f"{json_data.get("service", "unknown service")}-{json_data.get("user", "unknown user")}",
            identifier=post_id,
            title=json_data.get("title", "unknown title"),
            elements=elements,
        )
        if json_data.get("tags"):
            result["tags"] = scraper.TagsData(tags=json_data["tags"])
        return result

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)

        more_files = True
        params: dict[str, str | int] = {"o": 0}
        assert isinstance(params["o"], int)

        data: list[dict[Any, Any]] = []
        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_ARTIST_URL_POSTS.format(service=self.service, type=self.type, username=tagname), params=params)
            if res.status_code == 400:  # indicates a username instead of whichever ID this subservice is using
                new_tagname = await self.resolve_tagnames_to_id(tagname)
                if new_tagname == tagname:
                    return
                continue
            data = res.json()

            if "error" in data:
                if all(x in data["error"] for x in ("Offset", "is bigger than total count")):  # type: ignore
                    return

            for post in data:
                post_id = post["id"]

                if post_id in update_ids:
                    return
                post_data = await self._get_post_data(post_id=post_id, tagname=tagname)
                logging.debug("[%s] - Post data: %s", self.ME.upper(), json.dumps(post_data, indent=4, sort_keys=True))

                yield post_data

            more_files = bool(data)
            params["o"] += 50


class KemonoTypeUser(KemonoBase):
    @property
    def type(self) -> str:
        return "user"


@final
class KemonoAfdian(KemonoTypeUser):
    ME = "kemono-afdian"

    @property
    def service(self) -> str:
        return "afdian"


@final
class KemonoBoosty(KemonoTypeUser):
    ME = "kemono-boosty"

    @property
    def service(self) -> str:
        return "boosty"


@final
class KemonoDlsite(KemonoTypeUser):
    ME = "kemono-dlsite"

    @property
    def service(self) -> str:
        return "dlsite"


@final
class KemonoPixivfanbox(KemonoTypeUser):
    ME = "kemono-fanbox"

    @property
    def service(self) -> str:
        return "fanbox"


@final
class KemonoFantia(KemonoTypeUser):
    ME = "kemono-fantia"

    @property
    def service(self) -> str:
        return "fantia"


@final
class KemonoGumroad(KemonoTypeUser):
    ME = "kemono-gumroad"

    @property
    def service(self) -> str:
        return "gumroad"


@final
class KemonoPatreon(KemonoTypeUser):
    ME = "kemono-patreon"

    @property
    def service(self) -> str:
        return "patreon"


@final
class KemonoSubscribestar(KemonoTypeUser):
    ME = "kemono-subscribestar"

    @property
    def service(self) -> str:
        return "subscribestar"
