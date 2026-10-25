"""Main module for interacting with https://reddit.com/ ."""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any, ClassVar, Literal, final

import aiofiles.ospath as aiopath
import asynciolimiter
import bs4
import curl_cffi
import ffmpeg
import httpx

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

        post_id = json_data["id"]
        source = json_data["subreddit"]

        result = scraper.PostData(
            identifier=post_id,
            source=source,
            elements=scraper.PostElementData(data=json_data),
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
                post_data = await self._get_post_data(json_data=post["data"])
                if str(post_data["identifier"]) in update_ids:
                    return
                yield post_data

            after = data["after"]
            if after is None:
                return
            params["after"] = after

    async def _download_post_from_postelem_perwebsite(self, data: scraper.PostElementData, dpath: Path, filename: str) -> bool:
        post_element_data = data["data"]
        post_id = post_element_data["id"]
        post_url = post_element_data["url"]
        post_element_data = self.resolve_crossposts(post_element_data)

        if any(
            (removal_key in post_element_data.keys() and post_element_data[removal_key])
            for removal_key in ["removal_reason", "removed_by", "removed_by_category"]
        ):
            logging.error("[%s] - Skipped the download of image https://reddit.com/comments/%s , because it was removed.", self.ME.upper(), post_id)
            return True

        post_type = self.get_post_type(post_element_data, post_id=post_id, post_url=post_url)
        logging.info("[%s] - %s, Type %s", self.ME.upper(), post_id or post_url, post_type)

        success: bool
        match post_type:
            case "text":
                text = post_element_data["selftext"]
                success = await f.download_text(config=self.config, directory=dpath, filename=f"{filename}.txt", content=text)
            case "video":
                (download_url_video, download_url_audio), extension = self.get_download_urls_video(post_element_data)
                success = await self.download_post_video(
                    post_element_data, video_url=download_url_video, audio_url=download_url_audio, dpath=dpath, filename=filename, extension=extension
                )
            case "gallery":
                if (
                    ("gallery_data" not in post_element_data.keys())
                    or (not post_element_data["gallery_data"])
                    or ("items" not in post_element_data["gallery_data"].keys())
                    or (not post_element_data["gallery_data"]["items"])
                ):  # Returns False if no data is in there
                    logging.error("[%s] - %s - gallery data reported as invalid or removed.", self.ME.upper(), post_element_data["name"])
                    return False
                generator = self.get_download_urls_gallery(post_element_data)
                success = await self.download_post_gallery(dpath, filename, generator)
            case "weird gallery":
                try:
                    generator = self.get_download_urls_gallery(post_element_data)
                    success = await self.download_post_gallery(dpath, filename, generator)
                except KeyError:
                    logging.error("[%s] - %s - KeyError when downloading gallery.", self.ME.upper(), post_id)
                    return False
            case "image" | "link":
                success = await self.download_post_image(post_data=post_element_data, dpath=dpath, filename=filename)
            case _:
                logging.error("[%s] - %s - No downloader for posttype '%s' .", self.ME.upper(), post_element_data["id"], post_type)
                return False

        if success is False:
            logging.warning(
                "[%s] - No success (%s) returned while downloading %s - postType %s . Attempting general downloader... ",
                self.ME.upper(),
                success,
                post_element_data["id"],
                post_type,
            )
            success = await self.download_post_general_downloader(post_data=post_element_data, dpath=dpath, filename=filename)
            logging.error(
                "[%s] - No success returned while downloading %s - postType %s . General downloader has failed as well... ",
                self.ME.upper(),
                post_element_data["id"],
                post_type,
            )
        return success

    def get_post_type(self, post_data: dict[Any, Any], post_id: str | None = None, post_url: str | None = None) -> str | Literal[False]:
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
        elif "url" in post_data.keys() and f.match_extension(post_data["url"]) in ("jpg", "jpeg", "png", "gif", "gifv", "webp"):
            return "image"
        elif ("post_hint" in post_data.keys() and post_data["post_hint"] == "link") or ("url" in post_data.keys() and post_data["url"]):
            return "link"

        logging.warning("[%s] - Unknown reddit post type. Skipping download ( %s ).", self.ME.upper(), post_id or post_url or None)
        return False

    def resolve_crossposts(self, post_data: dict[Any, Any]) -> dict[Any, Any]:
        if "crosspost_parent" in post_data.keys() and "crosspost_parent_list" in post_data.keys():
            if post_data["crosspost_parent_list"]:  # If something is in this key
                post_data = post_data["crosspost_parent_list"][0]
        return post_data

    def get_download_urls_image(self, post_data: dict[Any, Any]) -> tuple[str, str | None]:
        extension = f.match_extension(post_data["url"])
        try:
            assert extension
            try:
                if extension != "gif":
                    return post_data["url"].replace("&amp;", "&"), extension
                url = post_data["preview"]["images"][0]["variants"]["mp4"]["source"]["url"]
                return url.replace("&amp;", "&"), "mp4"
            except KeyError:
                url = post_data["url"]
                return url.replace("&amp;", "&"), extension
        except AssertionError:
            return post_data["url"].replace("&amp;", "&"), None

    def get_download_urls_video(self, post_data: dict[Any, Any]) -> tuple[list[str], str]:
        video_url = post_data["secure_media"]["reddit_video"]["fallback_url"].replace("?source=fallback", "")
        audio_url = f'{video_url.split("DASH_")[0]}DASH_audio{video_url[-4:]}'
        extension = f.match_extension(video_url)
        assert extension
        return [video_url.replace("&amp;", "&"), audio_url.replace("&amp;", "&")], extension

    async def get_download_urls_gallery(self, post_data: dict[Any, Any]) -> AsyncGenerator[tuple[int, int, str, str]]:
        digits = cf.get_digits(len(post_data["gallery_data"]["items"]))
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
            yield counter, digits, file_url.replace("&amp;", "&"), extension

    async def get_download_urls_weirdgallery(self, post_data: dict[Any, Any]) -> AsyncGenerator[tuple[int, int, str, str]]:
        res = await self.request(post_data["url"])
        file_urls: list[str] = []
        soup = bs4.BeautifulSoup(res.text, "html.parser")
        images = soup.find("div", {"data-test-id": "post-content"})
        images = images.find_all("figure")  # type: ignore
        if images is None:
            raise ValueError("Images unexpectedly empty.")
        for image in images:
            file_urls.append(image.find("a")["href"])  # type: ignore

        digits = cf.get_digits(len(file_urls))
        for counter, file_url in enumerate(file_urls):
            extension = f.match_extension(file_url)
            assert extension
            yield counter, digits, file_url, extension

    async def download_post_video(
        self, post_data: dict[Any, Any], video_url: str, audio_url: str, dpath: Path, filename: str, extension: str
    ) -> bool:
        def merge_av_ffmpeg(path_video: Path, path_audio: Path, path_out: Path) -> None:
            ffmpeg.output(ffmpeg.input(str(path_video)), ffmpeg.input(str(path_audio)), str(path_out), vcodec="copy", acodec="aac").run(
                overwrite_output=True
            )

        async def merge_av_ffmpeg_async(path_video: Path, path_audio: Path, path_out: Path) -> None:
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor() as pool:
                await loop.run_in_executor(pool, merge_av_ffmpeg, path_video, path_audio, path_out)

        if self.config.settings.general.overwrite_existing_files or not await aiopath.isfile(dpath / f"{filename}.{extension}"):
            video_filename_temp = f"-temp-video.{extension}"
            audio_filename_temp = f"-temp-audio.{extension}"
            await self.LIMIT.wait()
            video = await f.download_file(
                self.config,
                url=video_url,
                headers=self.headers,
                path=dpath,
                filename=video_filename_temp,
                force_overwrite=True,
                no_impersonation=True,
            )
            await self.LIMIT.wait()
            audio = await f.download_file(
                self.config,
                url=audio_url,
                headers=self.headers,
                path=dpath,
                filename=audio_filename_temp,
                force_overwrite=True,
                no_impersonation=True,
            )
            if video and audio:
                path_video = dpath / f"-temp-video.{extension}"
                path_audio = dpath / f"-temp-audio.{extension}"
                path_out = dpath / f"{filename}.{extension}"
                await merge_av_ffmpeg_async(path_video, path_audio, path_out)
                path_video.unlink()
                path_audio.unlink()
                return True
            elif video:
                (dpath / video_filename_temp).replace(dpath / f"{filename}.{extension}")
                logging.warning(
                    "[%s] - Audio file not downloaded, video file renamed to output name. (some videos dont have an audio stream)", self.ME.upper()
                )
                return True
            elif audio:
                (dpath / audio_filename_temp).replace(dpath / f"{filename}.{extension}")
                logging.error("[%s] - Video file not downloaded, audio file renamed to output name. (this shouldn't happen)", self.ME.upper())
                return False
            else:
                logging.error(
                    "[%s] - Skipped '%s' // '%s', because neither video nor audio could be downloaded.",
                    self.ME.upper(),
                    post_data["title"],
                    post_data["name"],
                )
                return False
        return True

    async def download_post_gallery(self, dpath: Path, filename: str, entries: AsyncGenerator[tuple[int, int, str, str]]) -> bool:
        downloaded_counter = 0
        counter = -100
        async for counter, digits, file_url, extension in entries:
            gallery_filename = f"{filename}-{str(counter).zfill(digits)}.{extension}"
            await self.LIMIT.wait()
            downloaded_counter += await f.download_file(
                config=self.config, url=file_url, headers=self.headers, path=dpath, filename=gallery_filename, no_impersonation=True
            )
        return downloaded_counter == counter + 1  # +1 because counter is enum, not length

    async def download_post_image(self, post_data: dict[Any, Any], dpath: Path, filename: str) -> bool:
        download_url, extension = self.get_download_urls_image(post_data)
        success: bool = False

        ### Reddit links
        if re.match((r"(?:https?://)?(?:i\.|v\.|www\.|)?(?:(?:external-)?preview\.)?redd(?:\.it|ituploads\.com|it\.com)"), download_url):
            logging.info(
                "[%s] - Detected reddit link.",
                self.ME.upper(),
            )
            await self.LIMIT.wait()
            success = await f.download_file(
                config=self.config,
                url=download_url,
                headers=self.headers,
                path=dpath,
                filename=f"{filename}.{extension}",
                no_impersonation=True,
            )

        elif download_url == "":
            logging.info("[%s] - Skipped, because no URL was found. Often due to deleted posts.", self.ME.upper())
            return True

        else:
            logging.error("[%s] - Third party URL detected: %s . Can't be processed.", self.ME.upper(), download_url)
            success = True

        if success == "404":
            success = False
        return success

    async def download_post_general_downloader(self, post_data: dict[Any, Any], dpath: Path, filename: str) -> bool:
        ##Default / Simple Downloader
        download_url, extension = self.get_download_urls_image(post_data)
        success = False
        if extension:
            try:
                logging.info("[%s] - No specific downloader found. Using general downloader. This may not work!", self.ME.upper())
                await self.LIMIT.wait()
                success = await f.download_file(
                    self.config, download_url, self.headers, path=dpath, filename=f"{filename}.{extension}", no_impersonation=False
                )
                logging.info("[%s] - General downloader success: %s", self.ME.upper(), success)
                if success is True:
                    return success
            except ConnectionError, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout:
                logging.error(
                    "[%s] - ConnectionError encountered when attempting to download https://reddit.com/comments/%s using the default downloader.",
                    self.ME.upper(),
                    post_data["id"],
                )

            # If general fails, will try to download highest-res reddit preview image available
            logging.warning("[%s] - General downloader failed. Trying to download reddit previews.", self.ME.upper())
            try:
                success = True
                for preview_img in post_data["preview"]["images"]:
                    preview_url = preview_img["source"]["url"].replace("&amp;", "&")
                    tmp = f.match_extension(preview_url)
                    assert tmp
                    extension = tmp
                    try:
                        res = await self.request(url=preview_url)
                        if res.headers["Content-Length"] == "510":
                            logging.error(
                                "[%s] - Reddit preview is imgur removed file: https://reddit.com%s .", self.ME.upper(), post_data["permalink"]
                            )
                            return False
                        await self.LIMIT.wait()
                        success = success and await f.download_file(
                            config=self.config,
                            url=download_url,
                            request_content=res.content,
                            path=dpath,
                            filename=f"{filename}.{extension}",
                            no_impersonation=True,
                        )
                    except Exception as error:
                        logging.warning(
                            "[%s] - %s encountered when trying to download reddit preview: https://reddit.com%s .",
                            self.ME.upper(),
                            cf.get_full_class_name(error),
                            post_data["permalink"],
                        )
                        success = False
            except KeyError as error:
                logging.error(
                    "[%s] - %s encountered when trying to download reddit preview: https://reddit.com%s .",
                    self.ME.upper(),
                    cf.get_full_class_name(error),
                    post_data["permalink"],
                )
                return False

        if success is False:
            logging.error("[%s] - general downloder could not download post: https://reddit.com%s .", self.ME.upper(), post_data["permalink"])
        return success
