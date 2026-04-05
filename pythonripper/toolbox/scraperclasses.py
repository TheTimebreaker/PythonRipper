import logging
import random
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast, final, overload

import asynciolimiter
import asyncstdlib
import curl_cffi
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f


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


class PostElement(TypedDict):
    pass


class PostElementLinks(PostElement):
    download_url: str
    extension: str


class PostElementData(PostElement):
    data: dict[str, Any]


class PostElementSavelink(PostElement):
    savelink: str


class Scraper(ABC):
    HOMEPAGE: str
    POST_PATTERN: str

    ME: str
    LIMIT: asynciolimiter._BaseLimiter
    SPACE_REPLACE: str
    IS_GOOGLE_SEARCHABLE: bool = True
    session: curl_cffi.requests.AsyncSession | httpx.AsyncClient

    def __init__(self, config: cfg.Config) -> None:
        self.config = config
        self.headers: dict[str, str] = {}
        self.download_headers: dict[str, str] = {}
        self.history: f.SqlDownloadHistory | None = None
        self.blacklist_tags: list[str] = []

    @abstractmethod
    async def init(self) -> bool: ...

    def format_tagname(self, tagname: str) -> str:
        return tagname.replace(" ", self.SPACE_REPLACE)

    def blacklist_tag_found(self, data: PostData) -> bool:
        tags = data.get("tags")
        if not tags:
            return False

        combined_tags = (
            tags.get("artists", []) + tags.get("characters", []) + tags.get("parodies", []) + tags.get("metatags", []) + tags.get("tags", [])
        )
        if any(blacklist_tag in combined_tags for blacklist_tag in self.blacklist_tags):
            return True

        return False

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
        raise NotImplementedError()

    async def _download_post_from_postelem_savelink(self, data: PostElementSavelink, dpath: Path, filename: str) -> bool:
        return await f.download_link(self.config, data["savelink"], (dpath / filename).with_suffix(".txt"))

    async def _download_post_from_postelem(
        self, data: PostElement | PostElementLinks | PostElementData | PostElementSavelink, dpath: Path, filename: str
    ) -> bool:
        # PostElementData
        if data.get("data"):
            data = cast(PostElementData, data)
            return await self._download_post_from_postelem_perwebsite(data, dpath, filename)

        # PostElementSavelink
        elif data.get("savelink"):
            data = cast(PostElementSavelink, data)
            return await self._download_post_from_postelem_savelink(data, dpath, filename)

        # PostElementLinks
        elif data.get("download_url") and data.get("extension"):
            data = cast(PostElementLinks, data)
            download_url = data.get("download_url")
            extension = data.get("extension")
            if not isinstance(download_url, str) or not isinstance(extension, str):
                raise TypeError()
            return await f.download_file(
                config=self.config,
                url=download_url,
                headers=self.download_headers,
                path=dpath,
                filename=f"{filename}.{extension}",
            )
        else:
            raise NotImplementedError()

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
    def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[PostData]:
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
            dpath = self.config.dpath()

        if not ignore_download_history and self.history is not None and self.history.contains(post_id):
            logging.info("[%s] - Skipped download of %s: in download history.", self.ME.upper(), post_id)
            return True
        if not ignore_blacklist and self.blacklist_tag_found(data):
            logging.info("[%s] - Skipped download of %s: blacklisted tags found.", self.ME.upper(), post_id)
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
                logging.debug("[%s] - Download of post %s successful.", self.ME, data["identifier"])
            else:
                logging.debug("[%s] - Download of post %s failed.", self.ME, data["identifier"])
            downloaded_counter += success

        full_success = downloaded_counter == len_elements
        if full_success and not ignore_download_history and self.history is not None:
            self.history.add(post_id)

        return full_success


# init blacklist???


class GalleryScraper(Scraper): ...


class TaggableScraper(Scraper):
    URL_TAG: str | tuple[str]
    TAG_PATTERN: str

    def __init__(self, config: cfg.Config) -> None:
        super().__init__(config)
        self.init_blacklist()

    @abstractmethod
    async def does_this_exist(self, tagname: str) -> bool: ...

    def init_blacklist(self) -> None:
        self.blacklist_tags = cf.init_blacklist_tags("_")

    @overload
    async def download_tag(
        self,
        tagname: str,
        dpath: Path | None = None,
        update: bool = False,
        update_ids: list[str] | None = None,
        ignore_download_history: bool = False,
        ignore_blacklist: bool = False,
        *,
        custom_mode: Literal["deviantart"] | None = None,
        fetch_favorites: bool = False,
    ) -> bool: ...
    @overload
    async def download_tag(
        self,
        tagname: str,
        dpath: Path | None = None,
        update: bool = False,
        update_ids: list[str] | None = None,
        ignore_download_history: bool = False,
        ignore_blacklist: bool = False,
        *,
        custom_mode: Literal["newgrounds"] | None = None,
        fetch_favorites: bool = False,
        endpoint: Literal["art", "audio"] | None = None,
    ) -> bool: ...

    @overload
    async def download_tag(
        self,
        tagname: str,
        dpath: Path | None = None,
        update: bool = False,
        update_ids: list[str] | None = None,
        ignore_download_history: bool = False,
        ignore_blacklist: bool = False,
        *,
        custom_mode: Literal["reddit"] | None = None,
        endpoint: (
            Literal[
                "new",
                "hot",
                "top hour",
                "top day",
                "top week",
                "top month",
                "top year",
                "top all",
                "rising",
                "controversial hour",
                "controversial day",
                "controversial week",
                "controversial month",
                "controversial year",
                "controversial all",
            ]
            | None
        ) = None,
    ) -> bool: ...

    async def download_tag(
        self,
        tagname: str,
        dpath: Path | None = None,
        update: bool = False,
        update_ids: list[str] | None = None,
        ignore_download_history: bool = False,
        ignore_blacklist: bool = False,
        *,
        custom_mode: Literal["deviantart", "newgrounds", "reddit"] | None = None,
        fetch_favorites: bool = False,
        endpoint: str | None = None,
    ) -> bool:
        # Init arguments
        tagname = self.format_tagname(tagname)
        if not await self.does_this_exist(tagname):
            logging.error("[%s] - Tag %s was not detected as existing.", self.ME.upper(), tagname)
            return False

        if dpath is None:
            dpath = self.config.dpath()
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
            generator = self._fetch_posts(tagname, update_ids)
        elif custom_mode == "deviantart":
            generator = self._fetch_posts(tagname, update_ids, fetch_favorites=fetch_favorites)  # type: ignore
        elif custom_mode == "reddit":
            generator = self._fetch_posts(tagname, update_ids, endpoint=endpoint)  # type: ignore
        elif custom_mode == "newgrounds":
            generator = self._fetch_posts(tagname, update_ids, endpoint=endpoint, fetch_favorites=fetch_favorites)  # type: ignore
        async for i, post in asyncstdlib.enumerate(generator):
            print(f'Downloading {self.ME} tag "{tagname}" (#{i})')

            result = await self.download_post(
                data=post, dpath=dpath, ignore_blacklist=ignore_blacklist, ignore_download_history=ignore_download_history
            )

            if result is True:
                logging.info("[%s] - Download of %s was successful.", self.ME.upper(), post["identifier"])
            else:
                logging.error("[%s] - Download of %s was not successful.", self.ME.upper(), post["identifier"])

            downloaded_counter += result
            posts.append(post["identifier"])

        if len(posts) == 0:
            print(f"{self.ME.upper()} : {tagname} : Skipped : No new files!")
            return True

        if update:
            await f.write_update_file(posts, dpath, update_ids, None)

        return downloaded_counter == len(posts)


class BooruScraper(TaggableScraper):
    def __init__(self, config: cfg.Config) -> None:
        super().__init__(config)
        self.history = f.SqlDownloadHistory(self.ME, self.config)


# self, url, dpath, filename, ignore_download_history
# self, post_id, dpath, filename, ignore_download_history
# self, data, dpath, filename, ignore_download_history


class ArtistWebsiteScraper(Scraper):
    @final
    async def download_all_posts(self, dpath: Path | None = None, update: bool = False) -> bool:
        if dpath is None:
            dpath = self.config.dpath()

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


async def download_from_scraper_object(config: cfg.Config, obj_ref: type[Scraper], url: str, dpath: Path, filename: str | None = None) -> bool:
    try:
        ignore_blacklist = config.data["booru_third_party_linked"]["ignore_booru_blacklists"]
        ignore_history = config.data["booru_third_party_linked"]["ignore_booru_downloadhistory"]
        if not isinstance(ignore_blacklist, bool):
            ignore_blacklist = True
        if not isinstance(ignore_history, bool):
            ignore_history = True
    except KeyError:
        logging.error("The settings at 'booru_third_party_linked/ignore_booru_blacklists' or '/ignore_booru_downloadhistory' must be bools.")
        ignore_blacklist = True
        ignore_history = True

    obj = obj_ref(config=config)
    if not await obj.init():
        logging.error("[%s] - Download url %s from scraper object failed because initialization failed.", obj.ME.upper(), url)
        return False
    return await obj.download_post(url=url, dpath=dpath, filename=filename, ignore_blacklist=ignore_blacklist, ignore_download_history=ignore_history)


async def artist_website_updater(config: cfg.Config, obj_ref: type[ArtistWebsiteScraper]) -> bool:
    obj = obj_ref(config)
    if not await obj.init():
        return False

    print(f"Updating local copy of artist website {obj.ME}.")

    dpath = config.dpath() / "artist-websites" / obj.ME
    success = await obj.download_all_posts(dpath=dpath, update=True)
    if not success:
        logging.error("[%s-UPDATER] - Some issue occurred that prevented some images from being correctly downloaded", obj.ME.upper())
    print("=" * 50)
    return success


async def update_stuff(
    config: cfg.Config, obj_ref: type[TaggableScraper], update_type: Literal["tags", "artists"], *, tag_list: list[str] | None = None
) -> bool:
    obj = obj_ref(config)
    if not await obj.init():
        return False

    print(f"Updating local copy of {obj.ME} {update_type}.")
    print("=" * 50)
    print("=" * 50)

    # Load artist / tag list
    if tag_list is None:
        # import necessary here to prevent circular imports
        import pythonripper.toolbox.subscription_management as sm  # noqa: I001, RUF100

        if update_type == "artists":
            tag_object = sm.CombinedArtistFile(config)
        elif update_type == "tags":
            tag_object = sm.CombinedBooruFile(config)
        tag_list = tag_object.get_list(obj.ME)
    random.shuffle(tag_list)

    # Download
    full_success = True
    for i, tag in enumerate(tag_list):
        this_path = config.dpath() / obj.ME / f.verify_filename(tag)
        print(f"{i+1}/{len(tag_list)} - {tag} - {obj.ME}")
        this_path.mkdir(parents=True, exist_ok=True)
        try:
            success = await obj.download_tag(tagname=tag, dpath=this_path, update=True)
        except cf.ExtractorExitError:
            success = False
        except cf.ExtractorStopError:
            logging.critical(
                "[%s-%s-UPDATER] - Extractor was signaled to stop execution.",
                obj.ME.upper(),
                update_type.upper(),
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
