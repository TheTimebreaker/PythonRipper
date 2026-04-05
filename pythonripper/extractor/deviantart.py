"""Main module for interacting with https://www.deviantart.com/ ."""

import json
import logging
import re
import secrets
import threading
import time
import urllib.parse
import webbrowser
from collections.abc import AsyncGenerator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, final

import aiofiles
import asynciolimiter
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class OAuthResult:
    def __init__(self) -> None:
        self.code = None
        self.state = None
        self.error = None


class Credentials(TypedDict):
    client_id: str
    client_secret: str
    refresh_token: NotRequired[str]
    access_token: NotRequired[str]
    valid_until: NotRequired[float]


@final
class DeviantartAPI(scraper.TaggableScraper):
    # endpoints
    #     placebo: Checks, if authorization token (header) is still valid
    #     deviation/download/{deviationId}: Endpoint for requesting download info on a single image post

    HOMEPAGE = "https://deviantart.com/"
    API_URL = "https://www.deviantart.com/api/v1/oauth2/{endpoint}"
    URL_POST = "https://www.deviantart.com/deviation/{post_id}"
    URL_TAG = "https://deviantart.com/{tagname}"

    IMAGE_POST_PATTERN = r"(?:https?://)?(?:www\.)?deviantart\.com/([\w\d\-_]+)/art/([\w\d\-_]+)"
    POST_PATTERN = r"(?:https?://)?(?:www\.)?deviantart\.com/(?:[\w\d\-_]+/art/(?:[\w\d\-_]+\-|)|deviation/)(\d+)"
    FAVORITES_GALLERY_PATTERN = r"(?:https?://)?(?:www\.)?deviantart\.com/([\w\d\-_]+)/(favourites|gallery)/?([/\w\d\-_]*)?"
    TAG_PATTERN = r"https://(?:www\.)?deviantart\.com/([^/&\?]+)"

    ME = "deviantart"
    LIMIT = asynciolimiter.Limiter(1)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = True

    REDIRECT_PORT = 3055
    REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"

    session: httpx.AsyncClient
    allow_mature_content: bool

    async def init(self) -> bool:
        self.refresh_token: str | int
        self.headers: dict[str, str]
        self.valid_until: float | None = None
        self.credentials_path = self.config._credentials_path() / "deviantart_credentials.json"
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds())
        self.credentials: Credentials

        def calc_valid_until(expires_in: int | float) -> float:
            five_minutes = 60 * 5
            return expires_in + time.time() - five_minutes

        async def read_credentials() -> bool:
            try:
                async with aiofiles.open(self.credentials_path) as file:
                    data = json.loads(await file.read())
                    client_id = data["client_id"]
                    client_secret = data["client_secret"]
                    refresh_token = data["refresh_token"] if "refresh_token" in data else None

                    if refresh_token:
                        self.credentials = Credentials(
                            client_id=client_id,
                            client_secret=client_secret,
                            refresh_token=refresh_token,
                        )
                    else:
                        self.credentials = Credentials(
                            client_id=client_id,
                            client_secret=client_secret,
                        )

                    return True
            except FileNotFoundError, KeyError:
                logging.error(
                    "[DEVIANTART] - The credentials file at %s either does not exist or is invalid. "
                    "Refreshing API access token requires a client_id and client_secret in this file. "
                    "Please create an API access in a Deviantart account and enter the required values in the file.",
                    self.credentials_path,
                )
            return False

        async def write_credentials() -> bool:
            data = {
                "client_id": self.credentials["client_id"],
                "client_secret": self.credentials["client_secret"],
            }
            if self.credentials.get("refresh_token"):
                data["refresh_token"] = self.credentials["refresh_token"]
            async with aiofiles.open(self.credentials_path, "w") as file:
                await file.write(json.dumps(data, indent=4, sort_keys=True))
            return True

        async def get_refresh_token() -> bool:
            logging.info("[DEVIANTART] - Requesting account access and create refresh + access token.")
            expected_state = secrets.token_urlsafe(24)
            result = OAuthResult()

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:  # pylint: disable=invalid-name
                    parsed = urllib.parse.urlparse(self.path)
                    if parsed.path != "/callback":
                        self.send_response(404)
                        self.end_headers()
                        return

                    qs = urllib.parse.parse_qs(parsed.query)
                    result.code = qs.get("code", [None])[0]  # type: ignore
                    result.state = qs.get("state", [None])[0]  # type: ignore
                    result.error = qs.get("error", [None])[0]  # type: ignore

                    if result.error:
                        body = f"Authorization failed: {result.error}"
                    elif result.state != expected_state:
                        body = "State mismatch. You can close this window."
                    else:
                        body = "Authorization successful. You can close this window."

                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(body.encode("utf-8"))

                def log_message(self, _format: Any, *args: Any) -> None:
                    pass  # silence console logging

            server = HTTPServer(("127.0.0.1", self.REDIRECT_PORT), Handler)
            thread = threading.Thread(target=server.handle_request, daemon=True)
            thread.start()

            params = {
                "response_type": "code",
                "client_id": self.credentials["client_id"],
                "redirect_uri": self.REDIRECT_URI,
                "scope": "browse",
                "state": expected_state,
            }
            auth_url = "https://www.deviantart.com/oauth2/authorize?" + urllib.parse.urlencode(params)
            webbrowser.open(auth_url)

            thread.join(timeout=300)
            server.server_close()

            if result.error:
                raise RuntimeError(f"Authorization failed: {result.error}")
            if not result.code:
                raise RuntimeError("No authorization code received.")
            if result.state != expected_state:
                raise RuntimeError("State mismatch.")

            token_resp = await self.session.post(
                "https://www.deviantart.com/oauth2/token",
                auth=(self.credentials["client_id"], self.credentials["client_secret"]),
                data={
                    "grant_type": "authorization_code",
                    "code": result.code,
                    "redirect_uri": self.REDIRECT_URI,
                },
            )
            token_resp.raise_for_status()
            data = token_resp.json()

            self.credentials["access_token"] = data["access_token"]
            self.credentials["refresh_token"] = data["refresh_token"]

            self.credentials["valid_until"] = calc_valid_until(data.get("expires_in", 3600))

            return await write_credentials()

        async def refresh_access_token() -> bool:
            logging.info("[DEVIANTART] - Refreshing the access token.")
            params = {
                "grant_type": "refresh_token",
                "client_id": self.credentials["client_id"],
                "client_secret": self.credentials["client_secret"],
                "refresh_token": self.credentials["refresh_token"],
            }
            res = await self.session.post("https://www.deviantart.com/oauth2/token", params=params)
            if res.status_code == 429:
                raise cf.ExtractorStopError
            elif res.status_code != 200:
                raise cf.ExtractorStopError("Refreshing of refresh token failed: code %s - text %s ", res.status_code, res.text)

            access_token = res.json()["access_token"]
            refresh_token = res.json()["refresh_token"]
            expires_in = res.json()["expires_in"]
            if not isinstance(access_token, str) or not isinstance(refresh_token, str) or not isinstance(expires_in, (float, int)):
                raise ValueError("Refreshing of refresh token failed: invalid return types - text: ", res.text)

            self.credentials["access_token"] = access_token
            self.credentials["refresh_token"] = refresh_token
            self.credentials["valid_until"] = calc_valid_until(expires_in)

            return await write_credentials()

        def setup_header() -> bool:
            self.headers = {
                "Authorization": f"Bearer {self.credentials['access_token']}",
            }
            self.session.headers = self.headers
            return True

        def set_content_filters() -> bool:
            try:
                result = self.config.data["extractor"]["deviantart"]["allow_mature_content"]
                assert isinstance(result, bool)
                self.allow_mature_content = result
            except KeyError, AssertionError:
                logging.error(
                    "[DEVIANTART] - Settings for mature content not correctly set."
                    "Setting at extractor/deviantart/allow_mature_content must be bool."
                    "Defaulting to false."
                )
                self.allow_mature_content = False
            return True

        # Reads credentials from file
        if not await read_credentials():
            return False

        # Requests account access (and tokens) if they dont exist
        if not self.credentials.get("refresh_token"):
            if not await get_refresh_token():
                return False

        # Refreshes access token
        if not await refresh_access_token():
            return False

        # Sets up authorization headers
        if not setup_header():
            return False

        if not set_content_filters():
            return False

        return True

    async def does_this_exist(self, tagname: str) -> bool:
        url = f"https://www.deviantart.com/api/v1/oauth2/user/profile/{self.format_tagname(tagname)}"
        await self.LIMIT.wait()
        res = await self.session.get(url)
        if res.status_code == 429:
            raise cf.ExtractorStopError("Rate limited.")
        return res.status_code == 200

    async def _get_deviation_id(self, url: str | None = None, post_id: str | None = None) -> str:
        if url is None:
            if post_id is None:
                raise ValueError("Neither post_id nor url given (one is necessary).")
            url = self.URL_POST.format(post_id=post_id)

        await self.LIMIT.wait()
        res = await self.session.get(url, follow_redirects=True)
        if res.status_code == 429:
            raise cf.ExtractorStopError
        if res.status_code != 200:
            raise cf.ExtractorExitError("Could not get deviation id from %s : response status was not 200: %s", url or post_id, res.status_code)

        matched = re.search(r"DeviantArt://deviation/([\w\d\-]+)", res.text)
        if matched is None:
            raise cf.ExtractorExitError("Could not get deviation id from %s : regex could not find it", url or post_id)

        result = matched.group(1)
        if not isinstance(result, str):
            raise cf.ExtractorExitError("Could not get deviation id from %s : regex match is not a string", url or post_id)

        return result

    async def _get_folder_id(
        self, tagname: str, collection: str | None = None, endpoint: Literal["gallery", "favourites", "collections"] | None = None
    ) -> str:
        if collection is None:
            collection = "all"
        if collection.lower() == "all":
            return "all"
        if endpoint is None:
            endpoint = "gallery"

        tagname = self.format_tagname(tagname)
        if endpoint == "favourites":
            endpoint = "collections"

        params: dict[str, str | int] = {"username": tagname, "limit": 50, "offset": 0}
        assert isinstance(params["offset"], int)
        assert isinstance(params["limit"], int)

        while True:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL.format(endpoint=f"{endpoint}/folders"), params=params)
            if res.status_code == 429:
                raise cf.ExtractorStopError

            for entry in res.json()["results"]:
                entry_name = str(entry["name"])
                if collection.lower() == entry_name.lower():
                    return str(entry["folderid"])

            if res.json()["has_more"] is False:
                raise ValueError
            raise NotImplementedError("pagination needs to be verified")
            params["offset"] = res.json()["next_offset"]

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        """Post ID: the thing in your post url.

        Deviation ID: an API thing you basically only get when you know where to look."""
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")
            deviation_id = await self._get_deviation_id(post_id=post_id)

            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL.format(endpoint=f"deviation/{deviation_id}"))
            if res.status_code == 429:
                raise cf.ExtractorStopError
            json_data = res.json()

        source = json_data["author"]["username"]
        assert isinstance(source, str)

        post_id_match = re.match(self.POST_PATTERN, str(json_data["url"]))
        if post_id_match is None:
            raise cf.ExtractorExitError from ValueError
        post_id = post_id_match.group(1)
        assert isinstance(post_id, str)

        title = json_data["title"]
        assert isinstance(title, str)

        return scraper.PostData(
            identifier=post_id,
            source=source,
            title=title,
            elements=scraper.PostElementData(data=json_data),
        )

    async def _fetch_posts(
        self,
        tagname: str,
        update_ids: list[str] | None = None,
        folder_id: str | None = None,
        collection: str | None = None,
        fetch_favorites: bool = False,
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)

        if collection is None:
            collection = "all"

        endpoint: Literal["gallery", "favourites", "collections"]
        if fetch_favorites is True:
            endpoint = "collections"
        else:
            endpoint = "gallery"
        if folder_id is None:
            folder_id = await self._get_folder_id(tagname=tagname, collection=collection, endpoint=endpoint)

        params: dict[str, str | int | bool] = {"username": tagname, "limit": 24, "mature_content": self.allow_mature_content}

        more_files = True
        fetch_counter = 0
        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL.format(endpoint=f"{endpoint}/{folder_id}"), params=params)
            if res.status_code == 429:
                raise cf.ExtractorStopError

            for entry in res.json()["results"]:
                post_data = await self._get_post_data(json_data=entry)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            params["offset"] = res.json()["next_offset"]
            more_files = res.json()["has_more"]
            fetch_counter += 1
            return

    async def _download_post_from_postelem_perwebsite(self, data: scraper.PostElementData, dpath: Path, filename: str) -> bool:
        deviation_data = data["data"]

        post_url = deviation_data["url"]
        assert isinstance(post_url, str)
        post_id_matched = re.match(self.POST_PATTERN, post_url)
        assert post_id_matched
        post_id = post_id_matched.group(1)
        assert isinstance(post_id, str)

        # Skips watcher-only posts you dont have access on.
        # Example (NSFW) https://www.deviantart.com/mistressaipro/art/EVIL-DEAD-RISE-THE-BEAUTIFUL-EVIL-MUM-962228616
        if "premium_folder_data" in deviation_data:
            if not deviation_data["premium_folder_data"]["has_access"]:
                logging.info("[DEVIANTART] - Watcher-only post %s without access skipped. You can follow that artist to get access.", post_id)
                return True

        # Skips premium posts you dont have access to.
        # Example (NSFW) https://www.deviantart.com/keeksnsfw/art/Cowgirl-Chloe-V1-961836328
        if (
            "tier_access" in deviation_data.keys() and deviation_data["tier_access"] == "locked"
        ):  # If you dont have access: skip. Used for Paid-Subscriber-only content
            logging.info("[DEVIANTART] - Tier-access-locked data without access detected. Download skipped.")
            return True

        # Downloads image posts. Example (SFW) https://www.deviantart.com/sketchesbydani/art/Zombie-plants-963259561
        if "content" in deviation_data.keys():  # images
            logging.info("[DEVIANTART] - Image post detected.")

            file_url = deviation_data["content"]["src"]
            extension = f.match_extension(file_url)

            await self.LIMIT.wait()
            success = await f.download_file(self.config, file_url, headers=self.headers, path=dpath, filename=f"{filename}.{extension}")
            if success:
                logging.info("[DEVIANTART] - Download successful.")
            else:
                logging.error("[DEVIANTART] - Image post download unsuccessful. url %s", post_url)
            return success

        # Downloads video posts. Example (SFW) https://www.deviantart.com/charmingis/art/Aaravos-Sente-Mais-1302395606
        elif "videos" in deviation_data.keys() and deviation_data["videos"]:
            logging.info("[DEVIANTART] - Video post detected.")
            if not self.config.data["extractor"]["deviantart"]["saveVideoPosts"]:
                logging.info("[DEVIANTART] - Video post %s skipped due to config flag.", post_url)
                return True

            videos = []
            for video in deviation_data["videos"]:  # Loads all video urls, which have different video quality and therefore different filesizes
                videos.append([video["filesize"], video["src"]])
            videos.sort()  # sorts from small to big

            file_url = videos[-1][1]  # Link from biggest file
            extension = f.match_extension(file_url)

            await self.LIMIT.wait()
            success = await f.download_file(self.config, file_url, headers=self.headers, path=dpath, filename=f"{filename}.{extension}")
            if success:
                logging.info("[DEVIANTART] - Download successful.")
            else:
                logging.error("[DEVIANTART] - Video post download unsuccessful. url %s", post_url)
            return success

        # Downloads text posts, if config says do it. Literature Example (SFW) https://www.deviantart.com/hoaxdreams/art/Chainsmoker-962491467
        elif "text_content" in deviation_data:
            logging.info("[DEVIANTART] - Text post detected.")
            if not self.config.data["extractor"]["deviantart"]["saveTextPosts"]:
                logging.info("[DEVIANTART] - Text post %s skipped due to config flag.", post_url)
                return True

            logging.error(
                "[DEVIANTART] - Downloading text posts not supported, because when I tried fixing it after it broken, "
                "I realized deviantart sends back empty responses when you try to get texts."
            )
            return False

            await self.LIMIT.wait()
            res = await self.session.get(
                self.API_URL.format(endpoint="deviation/content"),
                params={"deviationid": deviation_data["deviationid"], "mature_content": True},
            )
            if res.status_code == 429:
                raise cf.ExtractorStopError

            text_url = res.json()["html"]
            extension = "txt"
            success = await f.download_text(self.config, dpath, f"{filename}.{extension}", text_url)
            if success:
                logging.info("[DEVIANTART] - Download successful.")
            else:
                logging.error("[DEVIANTART] - Text post download unsuccessful. url %s", post_url)
            return success

        # If no suitable downloader was found
        logging.error("[DEVIANTART] - Unsupported type of post. Skipping download. url %s.", post_url)
        return False
