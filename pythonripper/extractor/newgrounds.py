"""Main module for interacting with https://www.newgrounds.com/ ."""

import json
import logging
import re
from collections.abc import AsyncGenerator, Iterable
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any, Literal

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class NewgroundsAPI(scraper.TaggableScraper):
    # https://ARTIST.newgrounds.com
    # https://ARTIST.newgrounds.com/art DONE
    # https://ARTIST.newgrounds.com/audio DONE
    # https://ARTIST.newgrounds.com/news Not planned
    # https://ARTIST.newgrounds.com/favorites/art DONE
    # https://ARTIST.newgrounds.com/favorites/audio DONE
    # https://ARTIST.newgrounds.com/favorites/games Not planned
    # https://ARTIST.newgrounds.com/favorites/movies Not planned
    # https://ARTIST.newgrounds.com/favorites/following Not planned
    # https://ARTIST.newgrounds.com/playlists Not planned
    HOMEPAGE = "https://newgrounds.com"
    ARTIST_PAGE_BASE_URL = "https://{artist}.newgrounds.com/{sublink}"
    URL_TAG = "https://{tagname}.newgrounds.com"
    TAG_PATTERN = r"https://(?:www\.)?([^/&\?]+)\.newgrounds\.com"

    BASE_PATTERN = r"(?:https?://)?(?:www\.)?(.+)\.newgrounds\.com"
    POST_PATTERN = r"((?:https?://)?(?:www\.)newgrounds\.com/(?:art/view/[\w\d-]+|audio/listen|portal/view)/[\w\d\-]+)"
    ART_POST_PATTERN = r"(?:https?://)?(?:www\.)newgrounds\.com/art/view/([\w\d-]+)/([\w\d-]+)"
    AUDIO_POST_PATTERN = r"(?:https?://)?(?:www\.)newgrounds\.com/audio/listen/(\d+)"
    MOVIE_POST_PATTERN = r"(?:https?://)?(?:www\.)newgrounds\.com/portal/view/(\d+)"

    ME = "newgrounds"
    LIMIT = asynciolimiter.Limiter(1)
    SPACE_REPLACE = ""
    IS_GOOGLE_SEARCHABLE = True

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.jar_path = self.config._credentials_path() / "newgrounds_cookies.txt"
        self.suitabilites_config: dict[str, bool]
        self.csrf_token: str
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds())

        def load_newgrounds_cookies() -> bool:
            if not self.jar_path.is_file():
                logging.error(
                    "[%s] - Login via password unsupported. "
                    "Log into Newgrounds via your browser and export your cookies in the Netscape format via an extension."
                    "Rename the file to 'newgrounds_cookies.txt' and place it here: %s",
                    self.ME.upper(),
                    self.jar_path,
                )
                return False

            jar = MozillaCookieJar()
            jar.load(str(self.jar_path), ignore_discard=True, ignore_expires=True)

            for cookie in jar:
                self.session.cookies.set(
                    cookie.name,
                    cookie.value,  # type: ignore
                    domain=cookie.domain,
                    path=cookie.path,
                )
            return True

        async def start_session() -> bool:
            async def test_session(session: httpx.AsyncClient) -> bool:
                res = await session.get("https://www.newgrounds.com/art/view/afrobull/squirrel-girl-2")
                await f.atomic_write(Path("test.html"), res.text, encoding="utf-8-sig")
                if "You must be logged in, and at least 18 years of age to view this content" in str(res.text):
                    logging.error("[%s] - The session in-use does not allow accessing 18+ content. Please check manually!", self.ME.upper())
                    return False
                elif (
                    "https://art.ngfiles.com/medium_views/6319000/6319208_1552858_afrobull_untitled-6319208.05bbc025241b27d4934cfd93eacbb7bc.webp"
                    in str(res.text)
                ):
                    return True
                else:
                    logging.error(
                        "[%s] - The test_session function could not determine, whether or not the session can access 18+ content.", self.ME.upper()
                    )
                    return False

            if load_newgrounds_cookies() is not False:
                await self.LIMIT.wait()
                x = await self.session.get("https://www.newgrounds.com/social")
                assert isinstance(x, httpx.Response)
                test = x.text
                soup = bs4.BeautifulSoup(test, "html.parser")
                find = soup.find("form", {"method": "post"})

                if find is None:  # The cookies are valid!+
                    await update_suitabilities()
                    if await test_session(self.session):
                        return True
            logging.error(
                "[%s] - Loading cookies and using them was not successful. "
                "Delete the file %s and re-run script to get instructions on how to set new cookies.",
                self.ME.upper(),
                self.jar_path,
            )
            return False

        def suitabilities_from_config() -> bool:
            try:
                content_settings = self.config.data["extractor"]["newgrounds"]["content_ratings"]
                self.suitabilites_config = {
                    "e": bool(content_settings["e"]),
                    "t": bool(content_settings["t"]),
                    "m": bool(content_settings["m"]),
                    "a": bool(content_settings["a"]),
                }
                return True
            except KeyError:
                logging.error(
                    "[%s] - Could not read content filters from config."
                    'Please add them at ["extractor"]/["newgrounds"]/["content_ratings"]/["e"], /["t"], /["m"], /["a"]'
                    "as booleans.",
                    self.ME.upper(),
                )
                return False

        async def check_suitabilities() -> None:
            url = "https://www.newgrounds.com/art"
            await self.LIMIT.wait()
            res = await self.session.get(url)
            assert isinstance(res, httpx.Response)
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            finder = soup.find_all("input", {"type": "checkbox", "name": "suitabilities[]"})
            self.old_suitabilities = {"e": None, "t": None, "m": None, "a": None}
            for entry in finder:
                entry_type = entry["class"][0]
                self.old_suitabilities[entry_type] = entry.has_attr("checked") and entry["checked"] == "checked"  # type: ignore
            print(self.old_suitabilities)

        async def update_suitabilities() -> bool:
            logging.error("[%s] - Updating suitabilities does not work. Update them through the browser.", self.ME.upper())
            return False
            payload = {"suitabilities[]": [key for key in self.suitabilites_config.keys() if self.suitabilites_config[key] is True]}
            print(payload)
            await self.LIMIT.wait()
            res = await self.session.post("https://www.newgrounds.com/suitabilities", data=payload)
            print("suitabilities", res.status_code)

        if not suitabilities_from_config():
            return False

        if not await start_session():
            return False

        return True

    async def does_this_exist(self, tag_name: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(self.ARTIST_PAGE_BASE_URL.format(artist=self.format_tagname(tag_name), sublink=""))
        return res.status_code == 200

    def format_tagname(self, tagname: str) -> str:
        return tagname.replace(" ", self.SPACE_REPLACE).replace("(", "").replace(")", "")

    async def _get_audio_data(self, post_url: str) -> scraper.PostData:
        async def _iter_over_audio(audio_script_tag: bs4.Tag) -> AsyncGenerator[str]:
            text = audio_script_tag.string
            if not text:
                logging.error("[%s](A) - Could not extract download url from audio post %s ", self.ME.upper(), post_url)
                raise cf.InterruptError
            matched = re.search(r'"url":"(https:\\/\\/[^"]+\.mp3[^"]*)"', text)
            if not matched:
                logging.error("[%s](B) - Could not extract download url from audio post %s ", self.ME.upper(), post_url)
                raise cf.InterruptError

            url = matched.group(1).replace("\\/", "/")
            print(url)
            yield url

        res = await self.session.get(post_url)
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        # get parameters
        matched = re.match(self.AUDIO_POST_PATTERN, post_url)
        assert matched
        post_id = matched.group(1)
        artist = str(soup.find("div", {"class": "item-details"}).find("h4").find("a").contents[0])  # type: ignore
        post_title = str(soup.find("title").contents[0])  # type: ignore

        # get audio
        audio_script_tag = soup.find("script", string=re.compile("embedController"))  # type: ignore
        if audio_script_tag:
            generator = _iter_over_audio(audio_script_tag)
        else:
            raise NotImplementedError
        elements: list[scraper.PostElement] = []
        async for download_url in generator:
            extension = f.match_extension(download_url)
            if not extension:
                msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
                logging.error(msg)
                raise cf.ExtractorSkipError(msg) from AttributeError
            elements.append(scraper.PostElementLinks(download_url=download_url, extension=extension))

        return scraper.PostData(
            source=artist,
            identifier=post_id,
            title=post_title,
            elements=elements,
        )

    async def _get_art_data(self, post_url: str) -> scraper.PostData:
        async def _iter_over_single_image(image: bs4.Tag) -> AsyncGenerator[str]:
            logging.info("[%s] - Detected post as single image.", self.ME.upper())
            yield str(image["href"])

        async def _iter_over_art_image_row(images: Iterable[bs4.Tag]) -> AsyncGenerator[str]:
            logging.info("[%s] - Detected post as art image post(s).", self.ME.upper())
            for image in images:
                download_link_element = image.find("a", {"href": True})
                if download_link_element is None:
                    logging.error("[%s] - Could not download art_image_row %s : Couldn't find download link element.", self.ME.upper(), post_url)
                    raise cf.InterruptError
                yield str(download_link_element["href"])

        async def _iter_over_art_view_gallery(gallery: bs4.Tag) -> AsyncGenerator[str]:
            logging.info("[%s] - Detected post as art_view_gallery.", self.ME.upper())

            # yes the image data is in an inline script tag haha
            match = re.search(r"let imageData = (\[.*?\]);", str(gallery), re.DOTALL)
            if not match:
                logging.error(
                    "[%s] - Could not download art_view_gallery %s : Inline script tag with image data not found or unprocessable.",
                    self.ME.upper(),
                    post_url,
                )
                raise cf.InterruptError
            data = json.loads(match.group(1))
            for element in [img["image"] for img in data]:
                yield element

        logging.info("[%s] - %s", self.ME.upper(), post_url)
        res = await self.session.get(post_url)
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        # get parameters
        matched = re.match(self.ART_POST_PATTERN, post_url)
        assert matched
        artist, post_id = matched.groups()
        assert isinstance(artist, str) and isinstance(post_id, str)
        post_title = str(soup.find("title").contents[0])  # type: ignore

        # get images
        tmp = soup.find("div", {"class": "image"})
        if not tmp:
            msg = f"[{self.ME.upper()}] - Could not find div.image for {artist} - {post_id}"
            logging.error(msg)
            raise cf.ExtractorSkipError(msg) from AttributeError
        single_image = tmp.find("a", {"href": True})
        art_image_row = soup.find_all("div", {"class": "art-image-row"})
        art_view_gallery = soup.find("div", {"class": "art-view-gallery"})
        if single_image:
            generator = _iter_over_single_image(single_image)
        elif art_image_row:
            generator = _iter_over_art_image_row(art_image_row)
        elif art_view_gallery:
            generator = _iter_over_art_view_gallery(art_view_gallery)
        else:
            raise NotImplementedError
        elements: list[scraper.PostElement] = []
        async for download_url in generator:
            extension = f.match_extension(download_url)
            if not extension:
                msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
                logging.error(msg)
                raise cf.ExtractorSkipError(msg) from AttributeError
            elements.append(scraper.PostElementLinks(download_url=download_url, extension=extension))

        return scraper.PostData(
            source=artist,
            identifier=post_id,
            title=post_title,
            elements=elements,
        )

    async def _get_post_data(
        self, post_id: str | None = None, _json_data: dict[str, Any] | None = None, post_url: str | None = None
    ) -> scraper.PostData:

        if post_url is None:
            if post_id:
                post_url = post_id
            else:
                raise ValueError("Post url must be given, all other parameters are irrelevant.")

        if "audio/listen" in post_url:
            return await self._get_audio_data(post_url)
        if "art/view" in post_url:
            return await self._get_art_data(post_url)
        raise NotImplementedError

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, endpoint: Literal["art", "audio"] | None = None, fetch_favorites: bool = False
    ) -> AsyncGenerator[scraper.PostData]:
        def custom_selector(tag: bs4.element.Tag) -> bool:
            def art_selector(tag: bs4.element.Tag) -> bool:
                return tag.name == "a" and tag.has_attr("class") and "item-portalitem-art" in str(tag.get("class"))

            def audio_selector(tag: bs4.element.Tag) -> bool:
                return tag.name == "a" and tag.has_attr("class") and any(s in str(tag.get("class")) for s in ["item-audiosubmission", "item-link"])

            def movie_selector(tag: bs4.element.Tag) -> bool:
                return tag.name == "a" and tag.has_attr("class") and "inline-card-portalsubmission" in str(tag.get("class"))

            return art_selector(tag) or audio_selector(tag) or movie_selector(tag)

        if update_ids is None:
            update_ids = []
        if endpoint is None:
            endpoint = "art"

        tagname = self.format_tagname(tagname)

        last_art_pieces = None
        params = {
            "page": 0,
        }
        if fetch_favorites is True:
            url = self.ARTIST_PAGE_BASE_URL.format(artist=tagname, sublink=f"favorites/{endpoint}")
        else:
            url = self.ARTIST_PAGE_BASE_URL.format(artist=tagname, sublink=endpoint)

        while True:
            await self.LIMIT.wait()
            res = await self.session.get(url, params=params)
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            art_pieces = soup.find_all(custom_selector)

            # Breaks loop, when last found images are the same as the "new" ones - indicated the end of the webpage
            if art_pieces == last_art_pieces:
                return

            # For each found image, yield
            for art_piece in art_pieces:
                post_url = str(art_piece["href"])
                post_data = await self._get_post_data(post_url=post_url)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            params["page"] += 1
            last_art_pieces = art_pieces
