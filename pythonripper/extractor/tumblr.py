"""Main module for interacting with https://www.tumblr.com/ ."""

import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, final

import aiofiles
import asynciolimiter
import curl_cffi

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class TumblrAPI(scraper.TaggableScraper):
    API_URL = "https://api.tumblr.com"
    POST_PATTERN = r"(?:https?://)?(?:www\.)?tumblr\.com/([^/]+)/(\d+)/?"

    ME = "tumblr"
    LIMIT = asynciolimiter.LeakyBucketLimiter(300 / 60, capacity=290)
    SPACE_REPLACE = "_"

    params: dict[str, str | bool]

    async def init(self) -> bool:
        self.api_key: str
        self.credentials_path = self.config._credentials_path() / "tumblr_credentials.json"
        self.session = curl_cffi.requests.AsyncSession(timeout=cf.asynctimeoutseconds())

        async def get_api_key() -> bool:
            try:
                async with aiofiles.open(self.credentials_path) as file:
                    data = json.loads(await file.read())
                    self.api_key = data["api_key"]
                return True
            except FileNotFoundError:
                logging.error(
                    "[TUMBLR] - Credentials file not found at %s .",
                    self.credentials_path,
                )
            except KeyError:
                logging.error(
                    "[TUMBLR] - Invalid credentials file at %s .",
                    self.credentials_path,
                )
            logging.error(
                "[TUMBLR] - Please create an API key on your tumblr account and put it in a .json file at the above stated path. "
                "The file should contain the 'api_key' field set to the key you created.",
            )
            return False

        async def setup_session() -> bool:
            self.params = {
                "api_key": self.api_key,
                "npf": True,
            }
            self.session.params = self.params
            self.headers = {
                "User-Agent": "PythonRipper",
                "Content-Type": "application/json",
            }
            self.session.headers = self.headers
            self.download_headers = self.headers
            return True

        async def test_session() -> bool:
            await self.LIMIT.wait()
            response = await self.session.get(f"{self.API_URL}/v2/tagged", params={"tag": "anime"})
            return response.status_code == 200

        if not await get_api_key():
            return False

        if not await setup_session():
            return False

        if not await test_session():
            return False

        return True

    async def does_this_exist(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(f"{self.API_URL}/v2/blog/{self.format_tagname(tagname)}/info")
        return res.status_code == 200

    async def _get_post_data(
        self, post_id: str | None = None, json_data: dict[str, Any] | None = None, tagname: str | None = None
    ) -> scraper.PostData:
        if json_data is None:
            if post_id is None or tagname is None:
                raise ValueError("Neither post_id + username nor json_data given (one is necessary).")
            tagname = self.format_tagname(tagname)
            await self.LIMIT.wait()
            res = await self.session.get(f"{self.API_URL}/v2/blog/{tagname}/posts/photo", params={"id": post_id})
            if res.status_code != 200:
                logging.error("[TUMBLR] - %s %s : %s", tagname, post_id, res.status_code)
                raise cf.ExtractorExitError("%s %s : %s", tagname, post_id, res.status_code)
            json_data = res.json()["response"]["posts"][0]  # type: ignore

        post_id = str(json_data["id"])
        source = str(json_data["blog_name"])
        elements = [scraper.PostElementData(data=el) for el in json_data["content"]]

        return scraper.PostData(
            identifier=post_id,
            source=source,
            elements=elements,  # type: ignore
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        params: dict[str, str | int] = {}
        params["offset"] = 0
        more_files = True
        assert isinstance(params["offset"], int)

        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(f"{self.API_URL}/v2/blog/{tagname}/posts/photo", params=params)
            json_response = res.json()["response"]["posts"]  # type: ignore

            for post in json_response:
                post_data = await self._get_post_data(json_data=post, tagname=tagname)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            params["offset"] += 20
            more_files = bool(json_response)

    async def _download_file(self, url: str, dpath: Path, filename: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(url)
        return await f.download_file(config=self.config, path=dpath, filename=filename, request_content=res.content)

    async def __download_post_image(self, post_element_data: dict[str, Any], dpath: Path, filename: str | None) -> bool:
        logging.info("[TUMBLR] - Part of post detected as image.")

        best_image_height: int = -1
        best_image_url: str = ""

        for image in post_element_data["media"]:
            if "has_original_dimensions" in image.keys() and image["has_original_dimensions"]:
                best_image_url = image["url"]
                logging.info("[TUMBLR] - Original image found. Url: %s", image["url"])
                break
            else:
                if "height" in image.keys() and int(image["height"]) > best_image_height:
                    best_image_height = int(image["height"])
                    best_image_url = image["url"]
        else:
            logging.info("[TUMBLR] - No original image found, using best found. Url: %s", best_image_url)

        extension = f.match_extension(best_image_url)
        assert extension
        return await self._download_file(url=best_image_url, dpath=dpath, filename=f"{filename}.{extension}")

    async def __download_post_text(self, post_element_data: dict[str, Any], dpath: Path, filename: str | None) -> bool:
        logging.info("[TUMBLR] - Part of post detected as text.")
        if not self.config.data["extractor"]["tumblr"]["saveTextPosts"]:
            return True
        else:
            return await f.download_text(
                self.config, directory=dpath, filename=f"{filename}.txt", content=post_element_data["text"], encoding="utf-16"
            )

    async def __download_post_link(self, post_element_data: dict[str, Any]) -> bool:
        logging.info("[TUMBLR] - Part of post detected as video link.")
        return await f.download_link(self.config, post_element_data["url"])

    async def __download_post_video(self, post_element_data: dict[str, Any], dpath: Path, filename: str | None) -> bool:
        logging.info("[TUMBLR] - Part of post detected as video file.")
        extension = f.match_extension(post_element_data["media"]["url"])
        assert extension
        return await self._download_file(url=post_element_data["media"]["url"], dpath=dpath, filename=f"{filename}.{extension}")

    async def _download_post_from_postelem_perwebsite(self, data: scraper.PostElementData, dpath: Path, filename: str) -> bool:
        post_element_data = data["data"]
        if post_element_data["type"] == "image" and "media" in post_element_data.keys():
            return await self.__download_post_image(
                post_element_data,
                dpath=dpath,
                filename=filename,
            )

        elif post_element_data["type"] == "text":
            return await self.__download_post_text(
                post_element_data,
                dpath=dpath,
                filename=filename,
            )

        elif post_element_data["type"] == "video" and "url" in post_element_data.keys():
            return await self.__download_post_link(
                post_element_data,
            )

        elif post_element_data["type"] == "video" and "media" in post_element_data.keys():  # Video file
            return await self.__download_post_video(
                post_element_data,
                dpath=dpath,
                filename=filename,
            )

        elif post_element_data["type"] == "link":
            logging.info("[TUMBLR] - Part of post detected as link.")
            return await f.download_link(self.config, post_element_data["url"])

        elif post_element_data["type"] == "audio":
            logging.info("[TUMBLR] - Part of post detected as audio.")
            logging.error("[TUMBLR] - Audio link detected, but download not implemented, please check it manually: %s", post_element_data["url"])
            return False
        else:
            logging.info("[TUMBLR] - Part of post undetected.")
            return False
