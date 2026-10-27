import asyncio
import logging
import random
import re
import traceback
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast, final

import aiofiles.ospath as aiopath
import asynciolimiter
import asyncstdlib
import curl_cffi
import ffmpeg
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
from pythonripper.toolbox.config import ConfigObject
from pythonripper.toolbox.config.model.shared_model_data import AUDIO_FORMATS, IMAGE_FORMATS, VIDEO_FORMATS


class TagsData(TypedDict):
    artists: NotRequired[list[str]]
    characters: NotRequired[list[str]]
    metatags: NotRequired[list[str]]
    parodies: NotRequired[list[str]]
    tags: list[str]


class PostData(TypedDict):
    source: NotRequired[str]
    identifier: str
    title: NotRequired[str]
    filehash: NotRequired[str]
    elements: PostElement | list[PostElement]
    tags: NotRequired[TagsData]
    rating: NotRequired[str]


class PostElement(TypedDict):
    pass


class PostElementDownloadLinks(PostElement):
    download_url: str
    extension: str
    """File extension without the dot"""


class PostElementVideoDownloadLinks(PostElement):
    audio_url: str
    video_url: str
    extension: str
    """File extension without the dot"""


class PostElementData(PostElement):
    data: dict[str, Any]


class PostElementSavelink(PostElement):
    savelink: str


class PostElementText(PostElement):
    text: str


class PostElementEnum(StrEnum):
    DOWNLOAD_LINKS = "PostElementDownloadLinks"
    VIDEO = "PostElementVideoDownloadLinks"
    SAVELINK = "PostElementSavelink"
    TEXT = "PostElementText"

    DATA = "PostElementData"


def get_postelement_type(data: PostElement) -> PostElementEnum:
    if data.get("data", None) is not None:
        return PostElementEnum.DATA
    elif data.get("savelink", None) is not None:
        return PostElementEnum.SAVELINK
    elif data.get("download_url", None) is not None and data.get("extension", None) is not None:
        return PostElementEnum.DOWNLOAD_LINKS
    elif data.get("text", None) is not None:
        return PostElementEnum.TEXT
    elif data.get("audio_url", None) is not None and data.get("video_url", None) is not None:
        return PostElementEnum.VIDEO
    else:
        raise NotImplementedError(f"Unimplemented post element: {data}")


class Scraper(ABC):
    HOMEPAGE: str
    POST_PATTERN: str
    FILENAME_TO_ID_PATTERN: str

    WEBSITE_NAME: str
    ME: str
    LIMIT: asynciolimiter._BaseLimiter
    SPACE_REPLACE: str
    IS_CASE_SENSITIVE: bool = False
    ENCODE_URLS: bool = False
    DOWNLOAD_NOIMPERSONATION: bool = False

    session: curl_cffi.requests.AsyncSession | httpx.AsyncClient

    def __init__(self, config: ConfigObject) -> None:
        self.config = config

        self.headers: dict[str, str] = {}
        self.download_headers: dict[str, str] | None = None
        self.cookies: list[dict[str, str]] | None = None
        self.download_cookies: list[dict[str, str]] | None = None

        self.history: f.SqlDownloadHistory | None = None
        self.blacklist_tags: set[str] = set()
        self.init_blacklist()

    @abstractmethod
    async def init(self) -> bool: ...

    def format_tagname(self, tagname: str) -> str:
        return tagname.replace(" ", self.SPACE_REPLACE)

    def invert_formatting(self, formatted_tagname: str) -> str:
        map = {"&#039;": "'"}
        if not self.SPACE_REPLACE == "":  # prevents funky looking formattings
            map[self.SPACE_REPLACE] = " "

        for what, by in map.items():
            formatted_tagname = formatted_tagname.replace(what, by)
        return formatted_tagname

    def init_blacklist(self) -> None:
        self.blacklist_tags = self.config.settings.general.exclusions.blacklisted_tags
        if self.config.settings.general.exclusions.disallow_ai is True:
            bonus_tags: set[str]
            match self.ME:
                case "akairiot":
                    bonus_tags = set()
                case "animepictures":
                    bonus_tags = set()
                case "artstation":
                    bonus_tags = {"ai", "aigenerated", "midjourney", "createdwithaI"}
                case "danbooru":
                    bonus_tags = {
                        "ai-generated",
                        "ai-generated background",
                        "ai-assisted",
                        "dall-e",
                        "nai diffusion",
                        "midjourney",
                        "stable diffusion",
                    }
                # Deviantart blacklisting does not actually work, because there seemingly is no way of getting the tags from the API
                case "deviantart-tags" | "deviantart-artists" | "deviantart-favorites":
                    bonus_tags = {"aiart", "generatedart", "aigenerated", "aigeneratedart"}
                case "gelbooru":
                    bonus_tags = {
                        "ai",
                        "ai-generated",
                        "ai-generated background",
                        "ai-assisted",
                        "dall-e",
                        "midjourney",
                        "stable diffusion",
                    }
                # Hentaifoundry blacklisting does not actually work, because no API
                case "hentaifoundry" | "hentaifoundry-artists" | "hentaifoundry-tags":
                    bonus_tags = set()
                case "hypnohub":
                    bonus_tags = {"ai art"}
                case "kusowanka":
                    bonus_tags = {"ai-generated", "ai-generated background"}
                case "newgrounds-artists" | "newgrounds-favorites" | "newgrounds-tags":
                    bonus_tags = {
                        "ai-generated",
                        "ai-generated-pokemon",
                        "ai-assisted",
                        "dall-e",
                        "midjourney",
                        "stable-diffusion",
                        "ai generated",
                        "ai generated pokemon",
                        "ai assisted",
                        "dall e",
                        "stable diffusion",
                    }
                case "patreon":
                    bonus_tags = set()
                case "pixiv" | "pixiv-artists" | "pixiv-tags":
                    bonus_tags = {
                        "AIイラスト",
                        "Aiイラスト",
                        "aiイラスト",
                        "AI生成",
                        "Ai生成",
                        "ai生成",
                        "AI生成イラスト",
                        "Ai生成イラスト",
                        "ai生成イラスト",
                        "AI Generated",
                        "AI generated",
                        "Ai Generated",
                        "aI Generated",
                        "ai Generated",
                        "aI generated",
                        "Ai generated",
                        "ai generated",
                        "Ai绘画",
                        "AI绘画",
                        "ai绘画",
                        "aI绘画",
                        "AIGenerated",
                        "AIgenerated",
                        "AiGenerated",
                        "aIGenerated",
                        "Aigenerated",
                        "aIgenerated",
                        "aiGenerated",
                        "aIイラスト",
                        "aI生成",
                        "AIGeneratedイラスト",
                        "AIgeneratedイラスト",
                        "AiGeneratedイラスト",
                        "aIGeneratedイラスト",
                        "Aigeneratedイラスト",
                        "aIgeneratedイラスト",
                        "aiGeneratedイラスト",
                        "AI-Generated",
                        "AI-generated",
                        "Ai-Generated",
                        "aI-Generated",
                        "aI-generated",
                        "ai-Generated",
                        "AIGenerated illustration",
                        "AIgenerated illustration",
                        "AiGenerated illustration",
                        "aIGenerated illustration",
                        "Aigenerated illustration",
                        "aIgenerated illustration",
                        "aiGenerated illustration",
                    }
                case "reddit":
                    bonus_tags = set()
                case "rule34paheal":
                    bonus_tags = {"ai-generated", "stablediffusion"}
                case "rule34us":
                    bonus_tags = {
                        "ai generated",
                        "ai-generated",
                        "ai generated video",
                        "ai generated background",
                        "ai-generated background",
                        "ai-created",
                        "ai created",
                        "ai-assisted",
                        "ai assisted",
                        "stable diffusion",
                        "midjourney",
                    }
                case "rule34xxx":
                    bonus_tags = {
                        "ai",
                        "ai art",
                        "ai assisted",
                        "ai generated",
                        "ai-created",
                        "ai-generated",
                        "dalley le alpha",
                        "ai generated video",
                        "ai generated background",
                        "ai created",
                        "ai-assisted",
                        "stable diffusion",
                        "midjourney",
                    }
                case "rule34xyz" | "rule34world" | "rule34vault" | "furry34":
                    bonus_tags = {"ai generated", "ai-generated", "ai generated art (topic)"}
                case "shellvi":
                    bonus_tags = set()
                case "supersatanson":
                    bonus_tags = set()
                case "tangsgallery":
                    bonus_tags = set()
                case "tumblr":
                    bonus_tags = set()
                case "yandere":
                    bonus_tags = set()
                case _:
                    raise NotImplementedError(f"{self.ME} has no AI blacklisted tags hardcoded.")
            self.blacklist_tags.update(bonus_tags)

    def blacklist_tag_found(self, data: PostData) -> bool:
        tags = data.get("tags", None)
        if not tags:
            return False

        combined_tags = (
            tags.get("artists", []) + tags.get("characters", []) + tags.get("parodies", []) + tags.get("metatags", []) + tags.get("tags", [])
        )
        if self.IS_CASE_SENSITIVE is False:
            combined_tags = [x.lower() for x in combined_tags]
            self.blacklist_tags = {x.lower() for x in self.blacklist_tags}

        if any(blacklist_tag in combined_tags for blacklist_tag in self.blacklist_tags):
            return True

        return False

    def is_in_downloadhistory(self, data: PostData) -> bool:
        return self.history is not None and self.history.contains(data["identifier"])

    def is_content_rating_allowed(self, data: PostData) -> bool:  # noqa: ARG002
        return True

    def filename(
        self,
        number: int | None = None,
        filename: str | None = None,
        digits: int | None = None,
        source: str | None = None,
        post_id: str | int | None = None,
        post_title: str | None = None,
        file_hash: str | int | None = None,
    ) -> str:
        elems = [str(elem) for elem in (source, post_id, post_title, file_hash) if elem]
        if filename:
            pass
        elif len(elems) == 0:
            raise TypeError("Filename function called with no parameters called.")
        else:
            filename = f"{self.ME}_{"_".join(elems)}"
        if (number is None and digits is not None) or (number is not None and digits is None):
            raise TypeError(
                "Filename function was called with either a number or a digits parameter, indicating the usage of a counter. "
                "Both parameters are needed for a counter."
            )

        while filename.endswith((" ", ".")):
            filename = filename[:-1]

        if number is not None and digits is not None:
            return f"{filename}-{str(number).zfill(digits)}"
        return filename

    async def _download_post_from_postelem_perwebsite(self, data: PostElementData, dpath: Path, filename: str) -> bool:
        """Placeholder function for websites/classes who overwrite the entire downloading code with their own."""
        raise NotImplementedError()

    async def _download_post_from_postelem_savelink(self, data: PostElementSavelink, dpath: Path, filename: str) -> bool:
        return await f.download_link(self.config, data["savelink"], (dpath / f.verify_filename(filename)).with_suffix(".txt"))

    async def _download_post_from_postelem_video(self, data: PostElementVideoDownloadLinks, dpath: Path, filename: str) -> bool:
        def merge_av_ffmpeg(path_video: Path, path_audio: Path, path_out: Path) -> None:
            ffmpeg.output(
                ffmpeg.input(str(path_video)),
                ffmpeg.input(str(path_audio)),
                str(path_out),
                vcodec="copy",
                acodec="aac",
            ).run(overwrite_output=True)

        async def merge_av_ffmpeg_async(path_video: Path, path_audio: Path, path_out: Path) -> None:
            await asyncio.to_thread(merge_av_ffmpeg, path_video, path_audio, path_out)

        audio_url = data["audio_url"]
        video_url = data["video_url"]
        extension = data["extension"]
        if self.config.settings.general.overwrite_existing_files or not await aiopath.isfile(dpath / f"{filename}.{extension}"):
            video_filename_temp = f"-temp-video.{extension}"
            audio_filename_temp = f"-temp-audio.{extension}"
            args: dict[str, Any] = {
                "headers": self.download_headers,
                "cookies": self.download_cookies,
                "path": dpath,
                "filename": video_filename_temp,
                "force_overwrite": True,
                "no_impersonation": self.DOWNLOAD_NOIMPERSONATION,
            }

            await self.LIMIT.wait()
            video = await f.download_file(self.config, url=video_url, **args)
            await self.LIMIT.wait()
            audio = await f.download_file(self.config, url=audio_url, **args)

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
                    "[%s] - Skipped, because neither video nor audio could be downloaded.",
                    self.ME.upper(),
                )
                return False
        return True

    async def _download_post_from_postelem(
        self, data: PostElement | PostElementDownloadLinks | PostElementData | PostElementSavelink, dpath: Path, filename: str
    ) -> bool:
        data_type = get_postelement_type(data)
        match data_type:
            case PostElementEnum.DATA:
                data = cast(PostElementData, data)
                return await self._download_post_from_postelem_perwebsite(data, dpath, filename)
            case PostElementEnum.SAVELINK:
                data = cast(PostElementSavelink, data)
                return await self._download_post_from_postelem_savelink(data, dpath, filename)
            case PostElementEnum.DOWNLOAD_LINKS:
                data = cast(PostElementDownloadLinks, data)
                download_url = data.get("download_url")
                extension = data.get("extension")
                if not isinstance(download_url, str) or not isinstance(extension, str):
                    raise TypeError()
                return await f.download_file(
                    config=self.config,
                    url=download_url,
                    headers=self.download_headers,
                    cookies=self.download_cookies,
                    path=dpath,
                    filename=f"{filename}.{extension}",
                    no_impersonation=self.DOWNLOAD_NOIMPERSONATION,
                )
            case PostElementEnum.TEXT:
                data = cast(PostElementText, data)
                return await f.download_text(config=self.config, directory=dpath, filename=f"{filename}.txt", content=data["text"])
            case PostElementEnum.VIDEO:
                data = cast(PostElementVideoDownloadLinks, data)
                logging.error("[%s] - Not implemented: video download. data %s", self.ME.upper(), data)
                # needs to be tested when i find a video link
                # return await self._download_post_from_postelem_video(data, dpath, filename)  # noqa: ERA001
                return True
            case _:
                raise NotImplementedError(f"Unimplemented post element: {data}")

    def match_postid_from_url(self, url: str) -> list[str]:
        pattern = self.POST_PATTERN
        matched = re.match(pattern, url)
        if not matched:
            logging.error("[%s] - Could not gather post ID from url %s ", self.ME.upper(), url)
            raise cf.ExtractorExitError("Could not gather post ID from url %s ", url)

        out: list[str] = []
        for el in matched.groups():
            if not isinstance(el, str):
                raise cf.ExtractorExitError()
            out.append(el)

        return out

    @abstractmethod
    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> PostData: ...

    @abstractmethod
    def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False) -> AsyncGenerator[PostData]:
        """Fetches posts from tagname, taking update_ids into account.

        Newest posts will be yielded first."""
        ...

    async def download_post(
        self,
        url: str | None = None,
        post_id: str | None = None,
        tagname: str | None = None,
        data: PostData | None = None,
        dpath: Path | None = None,
        filename: str | None = None,
        ignore_download_history: bool = False,
        ignore_blacklist: bool = False,
        ignore_contentfilters: bool = False,
    ) -> bool:
        # Verify args
        if data is None:
            if post_id is None:
                if url is None:
                    raise ValueError("Neither data, nor post_id, nor url to post was given (one is necessary).")
                matched = self.match_postid_from_url(url)
                if len(matched) == 1:
                    post_id = matched[0]
                elif len(matched) == 2:
                    tagname, post_id = matched
                else:
                    raise NotImplementedError
            try:
                data = await self._get_post_data(post_id=post_id, tagname=tagname)  # type: ignore
            except TypeError:
                data = await self._get_post_data(post_id)
        post_id = str(data["identifier"])
        if dpath is None:
            dpath = self.config.paths.downloads()

        if not ignore_download_history and self.is_in_downloadhistory(data):
            logging.info("[%s] - Skipped download of %s: in download history.", self.ME.upper(), post_id)
            return True
        if not ignore_blacklist and self.blacklist_tag_found(data):
            logging.info("[%s] - Skipped download of %s: blacklisted tags found.", self.ME.upper(), post_id)
            return True
        if not ignore_contentfilters and not self.is_content_rating_allowed(data):
            logging.info("[%s] - Skipped download of %s: content rating disallowed.", self.ME.upper(), post_id)
            return True

        downloaded_counter = 0
        if not isinstance(data["elements"], list):
            data["elements"] = [data["elements"]]
        len_elements = len(data["elements"])
        digits_elements = cf.get_digits(len_elements)
        for i, element in enumerate(data["elements"]):
            if len_elements == 1:
                this_filename = self.filename(
                    filename=filename,
                    post_id=data["identifier"],
                    source=data.get("source"),
                    post_title=data.get("title"),
                    file_hash=data.get("filehash"),
                )
            else:
                this_filename = self.filename(
                    number=i,
                    digits=digits_elements,
                    filename=filename,
                    post_id=data["identifier"],
                    source=data.get("source"),
                    post_title=data.get("title"),
                    file_hash=data.get("filehash"),
                )

            element = cast(PostElement, element)
            await self.LIMIT.wait()
            success = await self._download_post_from_postelem(element, dpath=dpath, filename=this_filename)
            if success:
                logging.info("[%s] - Download of file #%s of post %s successful.", self.ME.upper(), i, data["identifier"])
            else:
                logging.error("[%s] - Download of file #%s of post %s failed.", self.ME.upper(), i, data["identifier"])
            downloaded_counter += success

        full_success = downloaded_counter == len_elements
        if full_success and not ignore_download_history and self.history is not None:
            self.history.add(post_id)

        return full_success


class GalleryScraper(Scraper): ...


class TaggableScraper(Scraper):
    URL_TAG: str | tuple[str, ...]
    TAG_PATTERN: str

    def __init__(self, config: ConfigObject) -> None:
        super().__init__(config)

    @abstractmethod
    async def does_this_exist(self, tagname: str) -> bool: ...

    async def does_this_have_posts(self, tagname: str) -> bool:
        async for _ in self._fetch_posts(tagname, ignore_contentfilters=True):
            return True
        return False

    async def download_tag(
        self,
        tagname: str,
        dpath: Path | None = None,
        update: bool = False,
        update_ids: list[str] | None = None,
        ignore_download_history: bool = False,
        ignore_blacklist: bool = False,
        ignore_contentfilters: bool = False,
        *,
        custom_mode: Literal["reddit"] | None = None,
        endpoint: str | None = None,
    ) -> bool:
        # Init arguments
        tagname = self.format_tagname(tagname)
        if not await self.does_this_exist(tagname):
            logging.error("[%s] - Tag %s was not detected as existing.", self.ME.upper(), tagname)
            return False

        if dpath is None:
            dpath = self.config.paths.downloads()
        if update_ids is None:
            update_ids = []
        if update:
            tmp = await f.read_update_file(dpath)
            assert isinstance(tmp, list)
            update_ids = tmp
        dpath.mkdir(parents=True, exist_ok=True)

        ### Downloads stuff
        downloaded_counter = 0
        posts: list[str] = []
        if not custom_mode:
            generator = self._fetch_posts(tagname, update_ids, ignore_contentfilters=ignore_contentfilters)
        elif custom_mode == "reddit":
            generator = self._fetch_posts(tagname, update_ids, ignore_contentfilters=ignore_contentfilters, endpoint=endpoint)  # type: ignore

        try:
            async for i, post in asyncstdlib.enumerate(generator):
                print(f'Downloading {self.ME} tag "{tagname}" (#{i})')

                try:
                    result = await self.download_post(
                        data=post,
                        dpath=dpath,
                        ignore_blacklist=ignore_blacklist,
                        ignore_download_history=ignore_download_history,
                        ignore_contentfilters=ignore_contentfilters,
                    )
                except cf.ExtractorExitError:
                    logging.error("[%s] - Download of %s lead to the extractor being forced to exit.", self.ME.upper(), post["identifier"])
                    raise
                except cf.ExtractorStopError:
                    logging.error("[%s] - Download of %s lead to the extractor being forced to stop.", self.ME.upper(), post["identifier"])
                    raise
                except cf.ExtractorSkipError:
                    logging.error("[%s] - Download of %s lead to the extractor being forced to skip this post.", self.ME.upper(), post["identifier"])
                    continue

                if result is True:
                    logging.info("[%s] - Download of %s was successful.", self.ME.upper(), post["identifier"])
                else:
                    logging.error("[%s] - Download of %s was not successful.", self.ME.upper(), post["identifier"])

                downloaded_counter += result
                posts.append(post["identifier"])
        except Exception as error:
            logging.error("[%s] - The generator failed to initialize or iterate. tag = %s", self.ME.upper(), tagname)
            raise cf.ExtractorStopError from error

        if len(posts) == 0:
            print(f"{self.ME.upper()} : {tagname} : Skipped : No new files!")
            return True

        if update:
            await f.write_update_file(posts, dpath, update_ids, None)

        # on the fly conversions
        if self.config.settings.general.image_conversion_settings.convert_while_downloading:
            for i, file in enumerate(dpath.iterdir()):
                print(f'Converting file "{file.name}" (#{i})')
                if file.suffix in IMAGE_FORMATS:
                    await f.image_converter_async(
                        file=file,
                        goal_format=self.config.settings.general.image_conversion_settings.target_format,
                        delete_source=True,
                        file_deletion_mode=self.config.settings.general.file_deletion_mode,
                        quality_setting=self.config.settings.general.image_conversion_settings.target_quality,
                        dimension_limiter=self.config.settings.general.image_conversion_settings.limit_dimensions,
                        dimension_limiter_value=self.config.settings.general.image_conversion_settings.limit_dimensions_value,
                    )
                elif file.suffix in AUDIO_FORMATS:
                    logging.error("[DOWNLOAD_TAG] - File conversion for %s not supported", file)
                elif file.suffix in VIDEO_FORMATS:
                    logging.error("[DOWNLOAD_TAG] - File conversion for %s not supported", file)
                elif file.suffix in (".txt", ".csv", ".bak", ".pythonripper") or file.name == ".pythonripper":
                    pass
                else:
                    logging.error("[DOWNLOAD_TAG] - File conversion for %s not supported", file)

        return downloaded_counter == len(posts)


class DownloadhistoryScraper(TaggableScraper):
    def __init__(self, config: ConfigObject) -> None:
        super().__init__(config)
        self.history = f.SqlDownloadHistory(self.WEBSITE_NAME, self.config)


# self, url, dpath, filename, ignore_download_history
# self, post_id, dpath, filename, ignore_download_history
# self, data, dpath, filename, ignore_download_history


class ArtistWebsiteScraper(Scraper):
    @final
    async def download_all_posts(self, dpath: Path | None = None, update: bool = False) -> bool:
        if dpath is None:
            dpath = self.config.paths.downloads()

        update_ids: list[str] = []
        if update:
            tmp = await f.read_update_file(dpath)
            assert isinstance(tmp, list)
            update_ids = tmp

        downloaded_counter = 0
        posts: list[PostData] = []
        async for post in self._fetch_posts("", update_ids=update_ids):
            success = await self.download_post(data=post, dpath=dpath)
            downloaded_counter += success
            if success:
                logging.info("[%s] - Successfully downloaded: %s ", self.ME.upper(), post["identifier"])
            else:
                logging.error("[%s] - Download unsuccessful: %s ", self.ME.upper(), post["identifier"])
            posts.append(post)

        if len(posts) == 0:
            print("Skipped - no new files found.")
        elif update:
            await f.write_update_file(posts, dpath, update_ids, "identifier")
        return downloaded_counter == len(posts)


async def artist_website_updater(config: ConfigObject, obj_ref: type[ArtistWebsiteScraper]) -> bool:
    obj = obj_ref(config)
    if not await obj.init():
        return False

    print(f"Updating local copy of artist website {obj.ME}.")

    dpath = config.paths.downloads() / "artist-websites" / obj.ME
    success = await obj.download_all_posts(dpath=dpath, update=True)
    if not success:
        logging.error("[%s-UPDATER] - Some issue occurred that prevented some images from being correctly downloaded", obj.ME.upper())
    print("=" * 50)
    return success


async def update_stuff(
    config: ConfigObject, obj_ref: type[TaggableScraper], update_type: Literal["tags", "artists", "favorites"], *, tag_set: set[str] | None = None
) -> bool:
    obj = obj_ref(config)
    if not await obj.init():
        return False

    print(f"Updating local copy of {obj.ME} {update_type}.")
    print("=" * 50)
    print("=" * 50)

    # Load artist / tag list
    if tag_set is None:
        # import necessary here to prevent circular imports
        import pythonripper.toolbox.subscription_management as sm  # noqa: I001, RUF100

        tag_object: sm.CombinedFile
        if update_type == "artists":
            tag_object = sm.combined_artist_file
        elif update_type == "tags":
            tag_object = sm.combined_tags_file
        elif update_type == "favorites":
            tag_object = sm.combined_favorites_file
        website = obj.ME
        tag_set = tag_object.get_list(website=website)
    tag_list = list(tag_set)
    random.shuffle(tag_list)

    # Download
    full_success = True
    for i, tag in enumerate(tag_list):
        bypass_markers = cf.parse_markers(tag)
        tag = bypass_markers["parsed"]
        ignore_blacklist = bypass_markers["blacklist_bypass"]
        ignore_contentfilters = bypass_markers["contentfilter_bypass"]

        this_path = config.paths.downloads() / obj.ME / f.verify_filename(tag)
        print(f"{i+1}/{len(tag_list)} - {tag} - {obj.ME}")
        this_path.mkdir(parents=True, exist_ok=True)
        try:
            success = await obj.download_tag(
                tagname=tag,
                dpath=this_path,
                update=True,
                ignore_blacklist=ignore_blacklist,
                ignore_contentfilters=ignore_contentfilters,
            )

        except cf.ExtractorExitError as error:
            tb = traceback.TracebackException.from_exception(error)
            logging.error(
                "[%s-%s-UPDATER] - Extractor signaled to exit current tag. Message : %s ",
                obj.ME.upper(),
                update_type.upper(),
                "".join(tb.format()),
            )
            success = False
        except cf.ExtractorStopError as error:
            tb = traceback.TracebackException.from_exception(error)
            logging.error(
                "[%s-%s-UPDATER] - Extractor was signaled to stop execution. Message : %s",
                obj.ME.upper(),
                update_type.upper(),
                "".join(tb.format()),
            )
            return False
        except httpx.HTTPStatusError as error:
            tb = traceback.TracebackException.from_exception(error)
            logging.error(
                "[%s-%s-UPDATER] - Extractor encountered a 4xx or 5xx HTTP response. Message : %s",
                obj.ME.upper(),
                update_type.upper(),
                "".join(tb.format()),
            )
            return False
        if not success:
            full_success = False
            logging.error(
                "[%s-%s-UPDATER] - Some issue occurred that prevented some images by %s %s being correctly downloaded.",
                obj.ME.upper(),
                update_type.upper(),
                update_type.upper(),
                tag,
            )
        print("=" * 50)
    return full_success
