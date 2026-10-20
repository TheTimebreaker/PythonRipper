"""Main module for interacting with https://www.rule34.xyz , https://www.rule34.world , https://www.rule34vault.com ."""

import logging
from collections.abc import AsyncGenerator, Mapping
from types import MappingProxyType
from typing import Any, Literal, final, override

import asynciolimiter
import asyncstdlib
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class _Rule34XyzWorldRoot(scraper.DownloadhistoryScraper):
    WEBSITE_PATTERN = r"(?:rule34\.(?:xyz|world)|(?:furry34|rule34vault)\.com)"
    WEBSITE_FILENAME_PATTERN = r"(?:rule34(?:xyz|world)|furry34|rule34vault)"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?" + WEBSITE_PATTERN + r"/post/(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?" + WEBSITE_PATTERN + r"/([^/&\?]+)"
    FILENAME_TO_ID_PATTERN = WEBSITE_FILENAME_PATTERN + r"_(\d+)_"

    HOMEPAGE: str
    CDN_HOMEPAGE: str
    URL_TAG: str
    APIURL_TAG: str
    APIURL_POST: str

    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"
    PER_PAGE = 60
    FORMATS = MappingProxyType(
        {
            "100": "mov.mp4",
            "101": "mov720.mp4",
            "102": "mov480.mp4",
            "10": "pic.jpg",
        }
    )

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.headers = {"User-Agent": "PythonRipper", "Accept": "application/json", "Accept-Encoding": "gzip,deflate,br"}
        self.session = httpx.AsyncClient(headers=self.headers)

        self.frontpage: set[str] = set()
        async for i, post in asyncstdlib.enumerate(self._fetch_posts(cf.id_generator(32))):
            self.frontpage.add(post["identifier"])
            if i >= (self.PER_PAGE):
                break

        return True

    def format_tagname(self, tagname: str) -> str:
        while tagname.startswith(" "):
            tagname = tagname[1:]
        while tagname.endswith(" "):
            tagname = tagname[:-1]
        return tagname.replace(" ", self.SPACE_REPLACE)

    async def request(
        self,
        url: str,
        params: Mapping[str, str | int] | None = None,
        json: Mapping[str, list[str] | str | int | bool] | None = None,
        method: Literal["get", "post"] = "get",
    ) -> httpx.Response:
        await self.LIMIT.wait()
        if method == "get":
            res = await self.session.get(url, params=params)
        elif method == "post":
            res = await self.session.post(url, params=params, json=json)
        else:
            raise NotImplementedError(f"Unsupported method: {method}")
        return res

    @override
    async def does_this_exist(self, tagname: str) -> bool:
        thispage = set()
        async for i, post in asyncstdlib.enumerate(self._fetch_posts(self.format_tagname(tagname))):
            thispage.add(post["identifier"])
            if i >= (self.PER_PAGE):
                break

        overlap = len(self.frontpage & thispage)
        return overlap < self.PER_PAGE / 2

    @override
    async def does_this_have_posts(self, tagname: str) -> bool:
        # this website will send back the frontpage if a tag does not exists
        # meaning that a tag that passes the does_this_exist will ALWAYS have posts
        return True

    @override
    def is_content_rating_allowed(self, data: scraper.PostData) -> bool:
        return True  # website exposes nothing in that regard

    async def _get_post_data(
        self, post_id: str | None = None, _json_data: dict[str, Any] | None = None, post_url: str | None = None
    ) -> scraper.PostData:
        def _get_post_downloadelements() -> list[scraper.PostElement]:
            try:
                api_files = resjson.get("files", None)
                if api_files is None:
                    raise cf.InterruptError
                if not isinstance(api_files, dict):
                    raise cf.InterruptError
                formats = self.FORMATS

                for format in formats:
                    if format in api_files:
                        root = self.CDN_HOMEPAGE if api_files[format][0] else self.HOMEPAGE
                        extension = formats[format]
                        if post_id is None:
                            raise ValueError
                        local_postid = int(post_id)

                        download_url = f"{root}/posts/{local_postid // 1000}/{local_postid}/{local_postid}.{extension}"
                        file_extension = f.match_extension(download_url)
                        if not file_extension:
                            raise cf.InterruptError
                        return [scraper.PostElementLinks(download_url=download_url, extension=file_extension)]
                raise cf.InterruptError
            except cf.InterruptError as error:
                logging.error("[%s] - Could not extract download URL from %s", self.ME.upper(), post_url)
                raise cf.ExtractorSkipError(f"Could not extract download URL from {post_url}") from error

        def _get_post_tags() -> scraper.TagsData:
            try:
                tags = resjson.get("tags", None)
                if not tags:
                    raise cf.InterruptError
                _artists: list[str] = []
                _characters: list[str] = []
                _metatags: list[str] = []
                _parodies: list[str] = []
                _tags: list[str] = []

                assert isinstance(tags, list)
                for tag in tags:
                    tagname = tag.get("value", None)
                    tagtype = tag.get("type", None)
                    if tagname is None:
                        raise cf.InterruptError
                    tagname = str(tagname)
                    assert isinstance(tagtype, int) or tagtype is None

                    match tagtype:
                        case None | 0 | 1:
                            _tags.append(tagname)
                        case 2:
                            _parodies.append(tagname)
                        case 4:
                            _characters.append(tagname)
                        case 8:
                            _artists.append(tagname)
                        case 16 | 32:
                            _metatags.append(tagname)
                        case _:
                            logging.error("[%s] - Unknown tag type %s", self.ME.upper(), tagtype)
                            raise cf.InterruptError

                return scraper.TagsData(artists=_artists, characters=_characters, metatags=_metatags, parodies=_parodies, tags=_tags)

            except cf.InterruptError:
                msg = f"Could not extract tags from {post_id}"
                logging.error("[%s] - %s", self.ME.upper(), msg)
                raise cf.ExtractorSkipError(msg) from ValueError

        if post_id is None:
            if _json_data is None:
                raise ValueError("Post ID or json data must be given.")
            post_id = _json_data.get("id")
            if not post_id:
                raise ValueError
            if any(field not in _json_data for field in ("tags", "files")):  # Refetch data if tags or files missing
                res = await self.request(self.APIURL_POST.format(postid=post_id))
                resjson: dict[str, int | str | list[dict[str, int | str]] | dict[str, list[int]]] = res.json()
        else:
            res = await self.request(self.APIURL_POST.format(postid=post_id))
            resjson = res.json()

        if not isinstance(resjson, dict):
            raise ValueError

        elements = _get_post_downloadelements()
        tags = _get_post_tags()

        return scraper.PostData(
            identifier=post_id,
            elements=elements,
            tags=tags,
        )

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False  # noqa: ARG002
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        api_url = self.APIURL_TAG
        params: dict[str, list[str] | int | bool] = {
            "includeTags": [tagname],
            "Skip": 0,
            "take": self.PER_PAGE,
            "CountTotal": False,
            "IncludeLinks": True,  # THIS DOES NOTHING BTW
            "OrderBy": 0,
        }
        while True:
            res = await self.request(api_url, json=params, method="post")
            data = res.json()
            items = data["items"]
            for post in items:
                post_data = await self._get_post_data(_json_data=post)
                identifier = post_data["identifier"]
                if str(identifier) in update_ids:
                    return

                yield post_data

            if len(items) < self.PER_PAGE:
                break

            params["Skip"] += self.PER_PAGE  # type: ignore # trust me its ok
            params["cursor"] = data["cursor"]


@final
class Furry34API(_Rule34XyzWorldRoot):
    HOMEPAGE = "https://furry34.com"
    CDN_HOMEPAGE = "https://furry34com.b-cdn.net"
    APIURL_TAG = "https://furry34.com/api/v2/post/search/root"
    APIURL_POST = "https://furry34.com/api/v2/post/{postid}"

    URL_TAG = "https://furry34.com/{tagname}"

    ME = "furry34"
    WEBSITE_NAME = "furry34"


@final
class Rule34VaultAPI(_Rule34XyzWorldRoot):
    HOMEPAGE = "https://rule34vault.com"
    CDN_HOMEPAGE = "https://r34xyz.b-cdn.net"
    APIURL_TAG = "https://rule34vault.com/api/v2/post/search/root"
    APIURL_POST = "https://rule34vault.com/api/v2/post/{postid}"

    URL_TAG = "https://rule34vault.com/{tagname}"

    ME = "rule34vault"
    WEBSITE_NAME = "rule34vault"

    ENCODE_URLS = True

    FORMATS = MappingProxyType(
        {
            "100": "mp4",
            "10": "jpg",
        }
    )

    def format_tagname(self, tagname: str) -> str:
        remove_dict: set[str] = {"."}
        for what in remove_dict:
            tagname = tagname.replace(what, "")
        return super().format_tagname(tagname)


@final
class Rule34WorldAPI(_Rule34XyzWorldRoot):
    HOMEPAGE = "https://rule34.world"
    CDN_HOMEPAGE = "https://rule34storage.b-cdn.net"
    APIURL_TAG = "https://rule34.world/api/v2/post/search/root"
    APIURL_POST = "https://rule34.world/api/v2/post/{postid}"

    URL_TAG = "https://rule34.world/{tagname}"

    ME = "rule34world"
    WEBSITE_NAME = "rule34world"


@final
class Rule34xyzAPI(_Rule34XyzWorldRoot):
    HOMEPAGE = "https://rule34.xyz"
    CDN_HOMEPAGE = "https://rule34xyz.b-cdn.net"
    APIURL_TAG = "https://rule34.xyz/api/v2/post/search/root"
    APIURL_POST = "https://rule34.xyz/api/v2/post/{postid}"

    URL_TAG = "https://rule34.xyz/{tagname}"

    ME = "rule34xyz"
    WEBSITE_NAME = "rule34xyz"
