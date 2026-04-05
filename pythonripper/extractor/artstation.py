"""Main module for interacting with https://www.artstation.com ."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, final

import asynciolimiter
import curl_cffi.requests

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class ArtstationAPI(scraper.TaggableScraper):

    # Post: https://www.artstation.com/artwork/{postid} | https://www.artstation.com/projects/{postid}.json
    # User: https://www.artstation.com/{username} | https://www.artstation.com/users/{username}/projects.json

    POST_PATTERN = r"(?:https?://)?(?:www\.)?artstation\.com/(?:artwork|projects)/([\w\d]+)"
    TAG_PATTERN = r"https://(?:www\.)?artstation\.com/(?:users/)?([^/&\?]+)"

    HOMEPAGE = "https://artstation.com/"
    API_URL_ARTIST = "https://www.artstation.com/users/{artist}/projects.json"
    API_URL_POST = "https://www.artstation.com/projects/{post_id}.json"
    URL_TAG = "https://artstation.com/{tagname}"

    ME = "artstation"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = True

    session: curl_cffi.requests.AsyncSession

    async def init(self) -> bool:
        self.headers = self.download_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
            "Accept-Language": "en-US,en;q=0.5",
        }
        self.session = curl_cffi.requests.AsyncSession(headers=self.headers, impersonate="chrome101")
        return True

    async def does_this_exist(self, tagname: str) -> bool:
        api_url = self.API_URL_ARTIST.format(artist=self.format_tagname(tagname))
        await self.LIMIT.wait()
        res = await self.session.get(api_url)
        return res.status_code == 200

    async def _get_post_data(self, post_id: str | None = None, _json_data: dict[Any, Any] | None = None) -> scraper.PostData:
        if post_id is None:
            raise ValueError("No post id given. Other fetching methods are impossible.")

        api_url = self.API_URL_POST.format(post_id=post_id)
        await self.LIMIT.wait()
        res = await self.session.get(api_url, headers=self.headers, impersonate="chrome101")

        if res.status_code != 200:
            logging.error("[ARTSTATION] - %s for downloading post %s . Impersonation?", res.status_code, post_id)
            raise cf.ExtractorExitError("%s for downloading post %s . Impersonation?", res.status_code, post_id)

        data = res.json()  # type: ignore
        artist = data["user"]["username"]
        elements: list[scraper.PostElement] = []
        for url in [asset["image_url"] for asset in data["assets"]]:
            assert isinstance(url, str)
            extension = f.match_extension(url)
            assert extension
            elements.append(scraper.PostElementLinks(download_url=url, extension=extension))
        post_hash = data["id"]

        return scraper.PostData(
            identifier=post_id,
            filehash=post_hash,
            elements=elements,
            source=artist,
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        api_url = self.API_URL_ARTIST.format(artist=tagname)
        params = {"page": 1}

        more_files = True
        update_encountered = False
        while more_files and not update_encountered:
            await self.LIMIT.wait()
            res = await self.session.get(api_url, params=params)

            if res.status_code != 200:
                logging.error("[ARTSTATION] - (artist json of %s) returned a non-200-HTML code. RIP. %s", tagname, res.status_code)
                raise cf.ExtractorExitError("(artist json of %s) returned a non-200-HTML code. RIP. %s", tagname, res.status_code)

            if not res.json()["data"]:  # type: ignore
                more_files = False
                return

            for post in res.json()["data"]:  # type: ignore
                identifier = post["hash_id"]  # artstation uses a hash-like to identify its posts; which makes all filename code here really confusing
                if str(identifier) in update_ids:
                    return
                yield await self._get_post_data(identifier)

            params["page"] += 1
