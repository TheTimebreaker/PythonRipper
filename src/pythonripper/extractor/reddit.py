"""Main module for interacting with https://reddit.com/ ."""

import logging
import re
from collections.abc import AsyncGenerator, Generator
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any, ClassVar, Literal, cast, final

import asynciolimiter
import curl_cffi

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class RedditAPI(scraper.TaggableScraper):
    HOMEPAGE = "https://reddit.com"
    IMAGE_PATTERN = r"(?:https?://)(?:i|(?:external-)?preview)\.redd(?:\.it|ituploads\.com)/[^/?#.]+\.([\w]{2,5})"
    VIDEO_PATTERN = r"(?:https?://)?v\.redd(?:\.it|ituploads\.com)/([^/?#.]+)/(?:[^?#.]+)\.([\w]{2,5})"
    POST_PATTERN = (
        r"(?:https?://)(?:www\.)?(?:i|(?:external-)?preview)?\.?redd(?:\.it|ituploads\.com|it\.com)"
        r"(?:(?:/r/|/u(?:ser)?/)\w+)?/(?:comments/)?([\w]{2,10})"
    )
    TAG_PATTERN = r"https://(?:www\.)?reddit\.com/((?:r|u|user)/[^/&\?]+)"

    BASE_URL = "https://api.reddit.com"
    POST_URL = BASE_URL + "/comments/{postId}"
    SUB_URL = BASE_URL + "/{subreddit}/{endpoint}"
    URL_TAG = (
        "https://www.reddit.com/r/{tagname}",
        "https://www.reddit.com/u/{tagname}",
        "https://www.reddit.com/user/{tagname}",
    )

    sublinks: ClassVar[dict[str, str]] = {
        "new": "new",
        "hot": "hot",
        "top hour": "top?t=hour",
        "top day": "top?t=day",
        "top week": "top?t=week",
        "top month": "top?t=month",
        "top year": "top?t=year",
        "top all": "top?t=all",
        "rising": "rising",
        "controversial hour": "controversial?t=hour",
        "controversial day": "controversial?t=day",
        "controversial week": "controversial?t=week",
        "controversial month": "controversial?t=month",
        "controversial year": "controversial?t=year",
        "controversial all": "controversial?t=all",
    }

    ME = "reddit"
    LIMIT = asynciolimiter.LeakyBucketLimiter(100 / 60, capacity=990)
    SPACE_REPLACE = "_"
    DOWNLOAD_NOIMPERSONATION = True

    session: curl_cffi.AsyncSession

    async def init(self) -> bool:
        self.jar_path = self.config.paths._credentials() / "reddit_cookies.txt"
        self.jar = MozillaCookieJar()
        self.session = curl_cffi.AsyncSession(timeout=cf.asynctimeoutseconds(), impersonate="chrome146")

        def read_cookie_file() -> bool:
            if not self.jar_path.is_file():
                logging.error(
                    "[%s] - Must be logged in via cookies. "
                    "Log into Reddit via your browser and export your cookies in the Netscape format via an extension."
                    "Rename the file to 'reddit_cookies.txt' and place it here: %s",
                    self.ME.upper(),
                    self.jar_path,
                )
                return False

            self.jar.load(str(self.jar_path), ignore_discard=True, ignore_expires=True)
            return True

        def apply_cookies_to_session() -> bool:
            for cookie in self.jar:
                self.session.cookies.set(
                    cookie.name,
                    cookie.value,  # type: ignore
                    domain=cookie.domain,
                    path=cookie.path,
                )
            return True

        async def test_session() -> bool:
            test_url = "https://www.reddit.com/r/Funny.json"
            res = await self.session.get(test_url)
            return res.status_code == 200

        if not read_cookie_file():
            logging.warning("[%s] - Reading cookie file failed!", self.ME.upper())
            return False
        if not apply_cookies_to_session():
            logging.warning("[%s] - Applying read cookies to session failed!", self.ME.upper())
            return False
        if not await test_session():
            logging.warning("[%s] - Testing session unsuccessful! Refresh your cookies and try again!", self.ME.upper())
            return False
        return True

    async def request(self, url: str, params: dict[str, str | int] | None = None) -> curl_cffi.Response:
        await self.LIMIT.wait()
        res = await self.session.get(url, params=params)
        if res.status_code == 403:
            msg = "A 403 was encountered, indicating that the cookies are no longer good."
            logging.critical("[%s] - %s", self.ME.upper(), msg)
            raise cf.ExtractorStopError(msg)
        return res

    async def does_this_exist(self, tagname: str) -> bool:
        tagname = self.format_tagname(tagname)
        res = await self.request(self.SUB_URL.format(subreddit=tagname, endpoint=""))
        resjson: dict[str, Any] = res.json()

        try:
            if resjson["reason"] in ("banned", "private"):
                logging.error("[%s] - Subreddit %s was banned or privated.", self.ME.upper(), tagname)
                return False
            elif resjson["message"] == "Not Found":
                logging.error("[%s] - Subreddit %s not available.", self.ME.upper(), tagname)
                return False
            elif res.status_code == 403 and resjson["reason"] in ("gated",):
                logging.error("[%s] - Subreddit %s was gated.", self.ME.upper(), tagname)
                return False
            elif res.status_code == 404 and resjson["message"] in ("Not Found",):
                logging.error("[%s] - Subreddit %s was not found (deleted?).", self.ME.upper(), tagname)
                return False
        except KeyError:
            pass
        validity: bool = res.status_code == 200 and bool(resjson) and bool(resjson["data"]["children"])
        if not validity:
            logging.error("[%s] - Subreddit %s could not be verified as existing. %s", self.ME.upper(), tagname, res.text)
        return validity

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")

            post_url = self.POST_URL.format(postId=post_id)
            res = await self.request(url=post_url)
            json_data = res.json()[0]["data"]["children"][0]["data"]
        else:
            post_url = self.POST_URL.format(postId=post_id)

        post_id = json_data["id"]
        source = str(json_data["subreddit"]).lower()
        post_element_data = self.__resolve_crossposts(json_data)

        if any(
            (removal_key in post_element_data.keys() and post_element_data[removal_key])
            for removal_key in ["removal_reason", "removed_by", "removed_by_category"]
        ):
            msg = f"Skipped the download of image https://reddit.com/comments/{post_id} , because it was removed."
            logging.error("[%s] - %s", self.ME.upper(), msg)
            raise cf.ExtractorSkipError(msg)

        post_type = self.__get_post_type(post_element_data, post_id=post_id, post_url=post_url)
        logging.info("[%s] - %s, Type %s", self.ME.upper(), post_id or post_url, post_type)
        elements: list[scraper.PostElement] | scraper.PostElement
        match post_type:
            case "text":
                text = post_element_data["selftext"]
                elements = scraper.PostElementText(text=text)
            case "video":
                (download_url_video, download_url_audio), extension = self.__get_download_urls_video(post_element_data)
                elements = []
                elements.append(
                    scraper.PostElementVideoDownloadLinks(
                        audio_url=download_url_audio,
                        video_url=download_url_video,
                        extension=extension,
                    )
                )
            case "gallery" | "weird gallery":
                if (
                    ("gallery_data" not in post_element_data.keys())
                    or (not post_element_data["gallery_data"])
                    or ("items" not in post_element_data["gallery_data"].keys())
                    or (not post_element_data["gallery_data"]["items"])
                ):
                    msg = f"{post_element_data["name"]} - gallery data reported as invalid or removed."
                    logging.error("[%s] - %s", self.ME.upper(), msg)
                    raise cf.ExtractorSkipError(msg)
                try:
                    elements = [
                        scraper.PostElementDownloadLinks(download_url=download_url, extension=extension)
                        for download_url, extension in self.__get_download_urls_gallery(post_element_data)
                    ]
                except KeyError as error:
                    msg = f"An exception occurred when processing the gallery https://reddit.com/comments/{post_id} ."
                    logging.error("[%s] - %s", self.ME.upper(), msg)
                    raise cf.ExtractorSkipError(msg) from error
            case "image" | "link":
                download_url, extension = self.__get_download_urls_image(post_element_data)  # type: ignore
                if extension and re.match(
                    (r"(?:https?://)?(?:i\.|v\.|www\.|)?(?:(?:external-)?preview\.)?redd(?:\.it|ituploads\.com|it\.com)"), download_url
                ):
                    logging.info("[%s] - Detected reddit link.", self.ME.upper())
                    elements = scraper.PostElementDownloadLinks(download_url=download_url, extension=extension)
                elif download_url == "":
                    logging.info("[%s] - Skipped, because no URL was found. Often due to deleted posts.", self.ME.upper())
                else:
                    logging.info("[%s] - Third party URL detected: %s . Will be saved.", self.ME.upper(), download_url)
                    elements = scraper.PostElementSavelink(savelink=download_url)
            case _:
                msg = f"{post_element_data["id"]} - No downloader for posttype '{post_type}' ."
                logging.error("[%s] - %s", self.ME.upper(), msg)
                raise cf.ExtractorSkipError(msg)

        result = scraper.PostData(
            identifier=post_id,
            source=source,
            elements=elements,
        )

        return result

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False, endpoint: str | None = None  # noqa: ARG002
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []
        if endpoint is None:
            endpoint = "hot"

        timerparam = None
        tagname = self.format_tagname(tagname)
        if len(self.sublinks[endpoint].split("?t=")) > 1:
            endpoint, timerparam = self.sublinks[endpoint].split("?t=")
        else:
            endpoint = self.sublinks[endpoint]

        url = self.SUB_URL.format(subreddit=tagname, endpoint=endpoint)
        params: dict[str, str | int] = {}
        if timerparam is not None:
            params["t"] = timerparam
        params["limit"] = 50

        while True:
            res = await self.request(url, params=params)

            data = res.json()["data"]
            if not data["children"]:  # Check for empty responses
                logging.warning(
                    "[%s] - A async-fetch-posts request to subreddit %s / endpoint %s was unexpectedly empty. Url: %s - headers: %s - params: %s",
                    self.ME.upper(),
                    tagname,
                    endpoint,
                    url,
                    self.headers,
                    params,
                )
                logging.warning("[%s] - %s", self.ME.upper(), res.text)
                logging.warning("[%s] - Status code: %s", self.ME.upper(), res.status_code)
                return

            for post in data["children"]:
                try:
                    post_data = await self._get_post_data(json_data=post["data"])
                except cf.ExtractorSkipError:
                    continue

                if str(post_data["identifier"]) in update_ids:
                    return
                yield post_data

            after = data["after"]
            if after is None:
                return
            params["after"] = after

    def __get_post_type(
        self, post_data: dict[Any, Any], post_id: str | None = None, post_url: str | None = None
    ) -> Literal["gallery", "video", "image", "text", "weird gallery", "link"]:
        if "is_gallery" in post_data.keys() and post_data["is_gallery"]:
            return "gallery"
        elif "is_video" in post_data.keys() and post_data["is_video"]:
            return "video"
        elif ("post_hint" in post_data.keys() and post_data["post_hint"] == "image") or re.match(self.IMAGE_PATTERN, post_data["url"]):
            return "image"
        elif post_data["selftext"] or "self." in post_data["domain"]:
            return "text"
        elif re.match(r"(?:https?://)?(?:www\.)?reddit\.com/gallery/[\w\d]+", post_data["url"]):
            logging.info("[%s] - Weird gallery detected.", self.ME.upper())
            return "weird gallery"  # this is where it is a gallery, but no image links are contained in the main post for some reason
        elif "url" in post_data.keys() and f.match_extension(post_data["url"]) in ("jpg", "jpeg", "jxl", "avif", "png", "gif", "gifv", "webp"):
            return "image"
        elif ("post_hint" in post_data.keys() and post_data["post_hint"] == "link") or ("url" in post_data.keys() and post_data["url"]):
            return "link"

        msg = f"Unknown reddit post type. Skipping download ( {post_id or post_url or None} )."
        logging.error("[%s] - %s", self.ME.upper(), msg)
        raise cf.ExtractorSkipError(msg)

    def __resolve_crossposts(self, post_data: dict[Any, Any]) -> dict[Any, Any]:
        if "crosspost_parent" in post_data.keys() and "crosspost_parent_list" in post_data.keys():
            if post_data["crosspost_parent_list"]:  # If something is in this key
                post_data = post_data["crosspost_parent_list"][0]
        return post_data

    def __get_download_urls_image(self, post_data: dict[Any, Any]) -> tuple[str, str | None]:
        extension = f.match_extension(post_data["url"])
        try:
            assert extension
            try:
                if extension != "gif":
                    return post_data["url"].replace("&amp;", "&"), extension
                url = post_data["preview"]["images"][0]["variants"]["mp4"]["source"]["url"]
                return url.replace("&amp;", "&"), "mp4"
            except KeyError:
                return post_data["url"].replace("&amp;", "&"), extension
        except AssertionError:
            return post_data["url"].replace("&amp;", "&"), None

    def __get_download_urls_video(self, post_data: dict[Any, Any]) -> tuple[list[str], str]:
        video_url = post_data["secure_media"]["reddit_video"]["fallback_url"].replace("?source=fallback", "")
        audio_url = f'{video_url.split("DASH_")[0]}DASH_audio{video_url[-4:]}'
        extension = f.match_extension(video_url)
        assert extension
        return [video_url.replace("&amp;", "&"), audio_url.replace("&amp;", "&")], extension

    def __get_download_urls_gallery(self, post_data: dict[Any, Any]) -> Generator[tuple[str, str]]:
        """Generates tuples of (file URL, file extension)"""
        for counter, image in enumerate(post_data["gallery_data"]["items"]):
            logging.info("[%s] - Gallery download URL generator #%s : %s", self.ME.upper(), counter, image)
            media_id = image["media_id"]
            if post_data["media_metadata"][media_id]["status"] == "failed":
                logging.error("[%s] - Failed to download image %s / %s.", self.ME.upper(), counter, len(post_data["media_metadata"]))
                continue
            elif post_data["media_metadata"][media_id]["status"] == "unprocessed":
                logging.error("[%s] - Failed to download unprocessed image %s / %s.", self.ME.upper(), counter, len(post_data["media_metadata"]))
                continue
            extension = post_data["media_metadata"][media_id]["m"].replace("image/", "")
            if extension in ("gif"):
                try:
                    file_url = post_data["media_metadata"][media_id]["s"]["mp4"]
                    extension = "mp4"
                except KeyError:
                    file_url = post_data["media_metadata"][media_id]["s"]["gif"]
            elif extension in ("jpg", "jpeg", "png"):
                file_url = post_data["media_metadata"][media_id]["s"]["u"]
            else:
                logging.error(
                    "[%s] - %s - No specific url extractor for this file extension found, using default one (may not properly work). %s / %s.",
                    self.ME.upper(),
                    post_data["name"],
                    counter,
                    len(post_data["media_metadata"]),
                )
                file_url = (post_data["media_metadata"][media_id]["s"]["u"],)
            yield file_url.replace("&amp;", "&"), extension

    async def _download_post_from_postelem(
        self,
        data: scraper.PostElement | scraper.PostElementDownloadLinks | scraper.PostElementData | scraper.PostElementSavelink,
        dpath: Path,
        filename: str,
    ) -> bool:
        data_type = scraper.get_postelement_type(data)
        match data_type:
            case scraper.PostElementEnum.DATA:
                pass
            case scraper.PostElementEnum.SAVELINK:
                data = cast(scraper.PostElementSavelink, data)
                if self.config.settings.extractor.reddit.save_thirdpartylinks_posts is False:
                    logging.info("[%s] - Link post %s skipped due to config flag.", self.ME.upper(), data["savelink"])
                    return True
            case scraper.PostElementEnum.DOWNLOAD_LINKS:
                data = cast(scraper.PostElementDownloadLinks, data)
                if self.config.settings.extractor.reddit.save_image_posts is False:
                    logging.info("[%s] - Image post %s skipped due to config flag.", self.ME.upper(), data["download_url"])
                    return True
            case scraper.PostElementEnum.TEXT:
                data = cast(scraper.PostElementText, data)
                if self.config.settings.extractor.reddit.save_text_posts is False:
                    logging.info("[%s] - Text post %s skipped due to config flag.", self.ME.upper(), data)
                    return True
            case scraper.PostElementEnum.VIDEO:
                data = cast(scraper.PostElementVideoDownloadLinks, data)
                if self.config.settings.extractor.reddit.save_video_posts is False:
                    logging.info("[%s] - Video post %s %s skipped due to config flag.", self.ME.upper(), data["audio_url"], data["video_url"])
                    return True
            case _:
                raise NotImplementedError(f"Unimplemented post element: {data}")

        return await super()._download_post_from_postelem(data, dpath, filename)
