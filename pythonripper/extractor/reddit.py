"""Main module for interacting with https://reddit.com/ ."""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, ClassVar, Literal, final

import aiofiles.ospath as aiopath
import asynciolimiter
import bs4
import ffmpeg
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.extractor import (
    animepictures,
    artstation,
    danbooru,
    deviantart,
    gelbooru,
    hentaifoundry,
    hypnohub,
    kusowanka,
    newgrounds,
    pixiv,
    rule34paheal,
    rule34us,
    rule34xxx,
    tumblr,
    yandere,
)


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
    IS_GOOGLE_SEARCHABLE = True

    session: httpx.AsyncClient
    third_party_save_link: list[str]
    third_party_ignore: list[str]
    third_party_download: list[str]

    async def init(self) -> bool:
        async def read_third_party_link_settings() -> bool:
            self.third_party_save_link = []
            self.third_party_ignore = []
            self.third_party_download = []
            data: dict[str, Any] = self.config.data
            try:
                reddit_data = data["extractor"]["reddit"]
                third_party_data: dict[str, Literal["save_link", "ignore", "download"]] = reddit_data["third_party_links"]
                for website, setting in third_party_data.items():
                    match setting:
                        case "download":
                            self.third_party_download.append(website)
                        case "ignore":
                            self.third_party_ignore.append(website)
                        case "save_link":
                            self.third_party_save_link.append(website)
                        case _:
                            raise ValueError(
                                "Some third party website settings were invalid. They must be set to either"
                                "'download', 'ignore' or 'save_link' EXACTLY."
                            )
            except KeyError:
                return False
            return True

        self.headers = self.download_headers = {"User-Agent": "PythonRipper-for-Reddit/0.0.1"}
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)
        if not await read_third_party_link_settings():
            return False
        return True

    async def does_this_exist(self, tagname: str) -> bool:
        tagname = self.format_tagname(tagname)
        await self.LIMIT.wait()
        res = await self.session.get(self.SUB_URL.format(subreddit=tagname, endpoint=""))
        await self.response_header_sleep(res.headers)
        try:
            if res.json()["reason"] in ("banned", "private"):
                logging.error("[%s] - Subreddit %s was banned or privated.", self.ME.upper(), tagname)
                return False
            elif res.json()["message"] == "Not Found":
                logging.error("[%s] - Subreddit %s not available.", self.ME.upper(), tagname)
                return False
            elif res.status_code == 403 and res.json()["reason"] in ("gated",):
                logging.error("[%s] - Subreddit %s was gated.", self.ME.upper(), tagname)
                return False
            elif res.status_code == 404 and res.json()["message"] in ("Not Found",):
                logging.error("[%s] - Subreddit %s was not found (deleted?).", self.ME.upper(), tagname)
                return False
        except KeyError:
            pass
        validity: bool = res.status_code == 200 and bool(res.json()) and bool(res.json()["data"]["children"])
        if not validity:
            logging.error("[%s] - Subreddit %s could not be verified as existing. %s", self.ME.upper(), tagname, res.text)
        return validity

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")

            post_url = self.POST_URL.format(postId=post_id)
            await self.LIMIT.wait()
            res = await self.session.get(url=post_url)
            await self.response_header_sleep(res.headers)
            json_data = res.json()[0]["data"]["children"][0]["data"]

        post_id = json_data["id"]
        source = json_data["subreddit"]
        title = json_data["title"]

        result = scraper.PostData(
            identifier=post_id,
            source=source,
            title=title,
            elements=scraper.PostElementData(data=json_data),
        )

        return result

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None, endpoint: str | None = None) -> AsyncGenerator[scraper.PostData]:
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
            await self.LIMIT.wait()
            res = await self.session.get(url, params=params)
            await self.response_header_sleep(res.headers)

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
                yield await self._get_post_data(post["data"])

            after = data["after"]
            if after is None:
                return
            params["after"] = after

    async def response_header_sleep(self, response_header: httpx.Headers) -> None:
        """Takes in the response header from any reddit request, searches for ratelimits
        and applies a sleep if you are too close to exceeding that limit."""
        try:
            remaining = round(float(response_header["x-ratelimit-remaining"]))
            reset_when = round(float(response_header["x-ratelimit-reset"]))
            logging.info("[%s] - remaining=%s, reset_when=%s", self.ME.upper(), remaining, reset_when)
            if remaining <= 3:
                timeout_seconds = reset_when + 1
                await asyncio.sleep(timeout_seconds)

        except KeyError:  # gets raised when python cant find the response
            pass

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
        await self.LIMIT.wait()
        res = await self.session.get(post_data["url"])
        await self.response_header_sleep(res.headers)
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

        if self.config.data["general"]["overwriteExistingFiles"] or not await aiopath.isfile(dpath / f"{filename}.{extension}"):
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

    async def _download_post_image_per_website(self, download_url: str, dpath: Path, filename: str) -> bool:
        success: bool = False
        if "anime-pictures" in download_url:
            logging.info("[%s] - Detected anime-pictures link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, animepictures.Animepictures, download_url, dpath, filename)
        elif "artstation" in download_url:
            logging.info("[%s] - Detected artstation link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, artstation.ArtstationAPI, download_url, dpath, filename)
        elif "danbooru" in download_url or "donmai" in download_url:
            logging.info("[%s] - Detected danbooru link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, danbooru.DanbooruAPI, download_url, dpath, filename)
        elif "deviantart" in download_url:
            logging.info("[%s] - Detected deviantart link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, deviantart.DeviantartAPI, download_url, dpath, filename)
        elif "gelbooru.com" in download_url:
            logging.info("[%s] - Detected gelbooru.com link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, gelbooru.GelbooruAPI, download_url, dpath, filename)
        elif "hentai-foundry.com" in download_url:
            logging.info("[%s] - Detected hentai-foundry.com link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, hentaifoundry.HentaiFoundry, download_url, dpath, filename)
        elif "hypnohub.net" in download_url:
            logging.info("[%s] - Detected hypnohub.net link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, hypnohub.HypnohubAPI, download_url, dpath, filename)
        elif "kusowanka.com" in download_url:
            logging.info("[%s] - Detected kusowanka.com link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, kusowanka.KusowankaAPI, download_url, dpath, filename)
        elif "newgrounds" in download_url:
            logging.info("[%s] - Detected newgrounds link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, newgrounds.NewgroundsAPI, download_url, dpath, filename)
        elif any(term in download_url for term in ("pximg", "pixiv")):
            logging.info("[%s] - Detected pixiv link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, pixiv.PixivArtistAPI, download_url, dpath, filename)
        elif "rule34.paheal.net" in download_url:
            logging.info("[%s] - Detected rule34.paheal.net link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, rule34paheal.Rule34pahealAPI, download_url, dpath, filename)
        elif "rule34.us" in download_url:
            logging.info("[%s] - Detected rule34.us link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, rule34us.Rule34usAPI, download_url, dpath, filename)
        elif "rule34.xxx" in download_url:
            logging.info("[%s] - Detected rule34.xxx link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, rule34xxx.Rule34xxxAPI, download_url, dpath, filename)
        elif "tumblr" in download_url:
            logging.info("[%s] - Detected tumblr link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, tumblr.TumblrAPI, download_url, dpath, filename)
        elif "yande.re" in download_url:
            logging.info("[%s] - Detected yande.re link.", self.ME.upper())
            success = await scraper.download_from_scraper_object(self.config, yandere.YandereAPI, download_url, dpath, filename)
        else:
            logging.error("[%s] - No image download wrapper for %s .", self.ME.upper(), download_url)
            success = False
        return success

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
                config=self.config, url=download_url, headers=self.headers, path=dpath, filename=f"{filename}.{extension}", no_impersonation=True
            )

        ### Writes links to file according to settings
        elif any(domain in download_url for domain in self.third_party_save_link):
            logging.info("[%s] - Writing a link to file according to settings.", self.ME.upper())
            await self.LIMIT.wait()
            return await f.download_file(self.config, download_url, headers=self.headers, no_impersonation=True)

        ### Skips links according to settings
        elif any(skip in download_url for skip in self.third_party_ignore):
            logging.info("[%s] - Skipped URL according to settings (skipped domain found).", self.ME.upper())
            return True

        ### Downloads third-party links according to settings
        elif any(download in download_url for download in self.third_party_download):
            logging.info("[%s] - Downloading third-party URL according to settings.", self.ME.upper())
            success = await self._download_post_image_per_website(download_url, dpath, filename)

        elif download_url == "":
            logging.info("[%s] - Skipped, because no URL was found. Often due to deleted posts.", self.ME.upper())
            return True

        else:
            logging.error("[%s] - Downloading third-party URL %s , despite it not being mentioned in the settings.", self.ME.upper(), download_url)
            success = await self._download_post_image_per_website(download_url, dpath, filename)

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
                success = await f.download_file(self.config, download_url, self.headers, dpath, f"{filename}.{extension}", no_impersonation=True)
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
                        await self.LIMIT.wait()
                        res = await self.session.get(url=preview_url)
                        await self.response_header_sleep(res.headers)
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
