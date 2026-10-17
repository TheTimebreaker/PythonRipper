"""Main module for interacting with https://www.newgrounds.com/ ."""

import json
import logging
import re
from collections.abc import AsyncGenerator, Iterable, Mapping
from http.cookiejar import MozillaCookieJar
from typing import Any, Literal

import asynciolimiter
import bs4
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.model import NewgroundsRating


class NewgroundsRootAPI(scraper.TaggableScraper):
    HOMEPAGE = "https://newgrounds.com"
    ARTIST_PAGE_BASE_URL = "https://{tagname}.newgrounds.com/{sublink}"
    TAG_PAGE_BASE_URL = "https://www.newgrounds.com/search/conduct/{sublink}"

    BASE_PATTERN = r"(?:https?://)?(?:www\.)?(.+)\.newgrounds\.com"
    POST_PATTERN = r"((?:https?://)?(?:www\.)newgrounds\.com/(?:art/view/[\w\d-]+|audio/listen|portal/view)/[\w\d\-]+)"
    ART_POST_PATTERN = r"(?:https?://)?(?:www\.)newgrounds\.com/art/view/([\w\d-]+)/([\w\d-]+)"
    AUDIO_POST_PATTERN = r"(?:https?://)?(?:www\.)newgrounds\.com/audio/listen/(\d+)"
    MOVIE_POST_PATTERN = r"(?:https?://)?(?:www\.)newgrounds\.com/portal/view/(\d+)"

    ME = "newgrounds"
    WEBSITE_NAME = "newgrounds"
    LIMIT = asynciolimiter.Limiter(1)

    session: httpx.AsyncClient
    endpoint: Literal["art", "audio", "games", "movies", "news", "playlists"]

    async def init(self) -> bool:
        self.jar_path = self.config.paths._credentials() / "newgrounds_cookies.txt"
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
            async def test_session() -> bool:
                res = await self.request("https://www.newgrounds.com/art/view/afrobull/squirrel-girl-2")
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
                x = await self.request("https://www.newgrounds.com/social")
                assert isinstance(x, httpx.Response)
                test = x.text
                soup = bs4.BeautifulSoup(test, "html.parser")
                find = soup.find("form", {"method": "post"})

                if find is None:  # The cookies are valid!+
                    await update_suitabilities()
                    if await test_session():
                        return True
            logging.error(
                "[%s] - Loading cookies and using them was not successful. "
                "Delete the file %s and re-run script to get instructions on how to set new cookies.",
                self.ME.upper(),
                self.jar_path,
            )
            return False

        def suitabilities_from_config() -> bool:
            content_settings = self.config.settings.extractor.newgrounds.content_ratings
            self.suitabilites_config = {
                "e": bool(NewgroundsRating.EVERYONE in content_settings),
                "t": bool(NewgroundsRating.TEEN in content_settings),
                "m": bool(NewgroundsRating.MATURE in content_settings),
                "a": bool(NewgroundsRating.ADULT in content_settings),
            }
            return True

        async def check_suitabilities() -> None:
            url = "https://www.newgrounds.com/art"
            res = await self.request(url)
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

        if not suitabilities_from_config():
            return False

        if not await start_session():
            return False

        return True

    async def request(self, url: str, params: Mapping[str, str | int] | None = None) -> httpx.Response:
        await self.LIMIT.wait()
        res = await self.session.get(url, params=params)
        return res

    def is_content_rating_allowed(self, data: scraper.PostData) -> bool:
        allowed_ratings = self.config.settings.extractor.newgrounds.content_ratings
        return data["rating"] in allowed_ratings

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
            yield url

        async def _iter_over_audio_podcasts(*args: bs4.Tag | None) -> AsyncGenerator[str]:
            for arg in args:
                if arg:
                    result = arg["content"]
                    yield str(result)

        res = await self.request(post_url)
        soup = bs4.BeautifulSoup(res.text, "html.parser")

        # get parameters
        matched = re.match(self.AUDIO_POST_PATTERN, post_url)
        assert matched
        post_id = matched.group(1)
        artist = str(soup.find("div", {"class": "item-details"}).find("h4").find("a").contents[0])  # type: ignore
        post_title = str(soup.find("title").contents[0])  # type: ignore

        # get audio
        audio_script_tag = soup.find("script", string=re.compile("embedController"))
        audio_meta_ogaudio = soup.find("meta", {"property": "og:audio"})  # podcasts??? # e.g. https://www.newgrounds.com/audio/listen/1484204
        audio_meta_ogimage = soup.find("meta", {"property": "og:image"})
        if audio_script_tag:
            generator = _iter_over_audio(audio_script_tag)
        elif audio_meta_ogaudio or audio_meta_ogimage:
            generator = _iter_over_audio_podcasts(audio_meta_ogaudio, audio_meta_ogimage)
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

        # get tags
        tags_parent = soup.find("dd", {"class": "tags"})
        tags: list[str] = []
        if tags_parent:
            tags_elems = tags_parent.find_all("a")
            for tag_elem in tags_elems:
                tags.append(str(tag_elem.contents[0]))

        # get rating
        rating_element = soup.find("dl", {"data-rating": True})
        if not rating_element:
            logging.error("[%s] - Could not find content rating element from post %s", self.ME.upper(), post_url)
            raise cf.ExtractorSkipError("Could not find content rating element from post %s", post_url) from KeyError
        rating_element_str = rating_element["data-rating"]
        if not rating_element_str:
            logging.error("[%s] - Could not extract content rating from post %s", self.ME.upper(), post_url)
            raise cf.ExtractorSkipError("Could not extract content rating from post %s", post_url) from KeyError
        if rating_element_str == "a":
            rating = NewgroundsRating.ADULT
        elif rating_element_str == "m":
            rating = NewgroundsRating.MATURE
        elif rating_element_str == "t":
            rating = NewgroundsRating.TEEN
        elif rating_element_str == "e":
            rating = NewgroundsRating.EVERYONE
        else:
            logging.error("[%s] - Could not find content rating from post %s", self.ME.upper(), post_url)
            raise cf.ExtractorSkipError("Could not find content rating from post %s", post_url) from KeyError

        return scraper.PostData(
            source=artist,
            identifier=post_id,
            title=post_title,
            elements=elements,
            rating=rating,
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
        res = await self.request(post_url)
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
        if art_image_row:
            generator = _iter_over_art_image_row(art_image_row)
        elif art_view_gallery:
            generator = _iter_over_art_view_gallery(art_view_gallery)
        elif single_image:
            generator = _iter_over_single_image(single_image)
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

        # get tags
        tags_parent = soup.find("dd", {"class": "tags"})
        tags: list[str] = []
        if tags_parent:
            tags_elems = tags_parent.find_all("a")
            for tag_elem in tags_elems:
                tags.append(str(tag_elem.contents[0]))

        # get rating
        rating_heading_adult = soup.find("h2", {"class": "rated-a"})
        rating_heading_teen = soup.find("h2", {"class": "rated-t"})
        rating_heading_mature = soup.find("h2", {"class": "rated-m"})
        rating_heading_everyone = soup.find("h2", {"class": "rated-e"})
        if rating_heading_adult:
            rating = NewgroundsRating.ADULT
        elif rating_heading_mature:
            rating = NewgroundsRating.MATURE
        elif rating_heading_teen:
            rating = NewgroundsRating.TEEN
        elif rating_heading_everyone:
            rating = NewgroundsRating.EVERYONE
        else:
            logging.error("[%s] - Could not find content rating from post %s", self.ME.upper(), post_url)
            raise cf.ExtractorSkipError("Could not find content rating from post %s", post_url) from KeyError

        return scraper.PostData(
            source=artist,
            identifier=post_id,
            title=post_title,
            elements=elements,
            tags=scraper.TagsData(tags=tags),
            rating=rating,
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
        if "movies" in post_url:
            raise NotImplementedError
        raise NotImplementedError

    def post_selector(self, tag: bs4.element.Tag) -> bool:
        """Selector for bs4.BeautifulSoup.find / findall methods.
        Returns the HTML tags containing the posts url in the 'href' field."""

        def art_selector(tag: bs4.element.Tag) -> bool:
            return tag.name == "a" and tag.has_attr("class") and "item-portalitem-art" in str(tag.get("class"))

        def audio_selector(tag: bs4.element.Tag) -> bool:
            return tag.name == "a" and tag.has_attr("class") and any(s in str(tag.get("class")) for s in ["item-audiosubmission", "item-link"])

        def movie_selector(tag: bs4.element.Tag) -> bool:
            return tag.name == "a" and tag.has_attr("class") and "inline-card-portalsubmission" in str(tag.get("class"))

        return art_selector(tag) or audio_selector(tag) or movie_selector(tag)


class _NewgroundsUserRootAPI(NewgroundsRootAPI):
    URL_TAG = "https://{tagname}.newgrounds.com"
    TAG_PATTERN = r"https://(?:www\.)?([^/&\?]+)\.newgrounds\.com"

    SPACE_REPLACE = ""
    fetch_favorites: bool

    async def does_this_exist(self, tagname: str) -> bool:
        url = self.ARTIST_PAGE_BASE_URL.format(tagname=self.format_tagname(tagname), sublink="")
        res = await self.request(url)
        return res.status_code == 200

    def format_tagname(self, tagname: str) -> str:
        replace_dict: dict[str, str] = {
            " ": self.SPACE_REPLACE,
        }
        remove_dict: set[str] = {"(", ")", "[", "]", "{", "}", ":", ".", "|", "!", "?", '"', "'", "§", "$", "%", "&", "/"}
        for what, by in replace_dict.items():
            tagname = tagname.replace(what, by)
        for what in remove_dict:
            tagname = tagname.replace(what, "")
        if self.SPACE_REPLACE * 2 in tagname:
            tagname = tagname.replace(self.SPACE_REPLACE * 2, self.SPACE_REPLACE, 1)
        return tagname

    def _fetch_posts(
        self,
        tagname: str,
        update_ids: list[str] | None = None,
        ignore_contentfilters: bool = False,
    ) -> AsyncGenerator[scraper.PostData]:
        return self._unified_fetch_posts(
            tagname=tagname,
            update_ids=update_ids,
            ignore_contentfilters=ignore_contentfilters,
            endpoint=self.endpoint,
            fetch_favorites=self.fetch_favorites,
        )

    async def _unified_fetch_posts(
        self,
        tagname: str,
        update_ids: list[str] | None = None,
        ignore_contentfilters: bool = False,  # noqa: ARG002
        endpoint: Literal["art", "audio", "games", "movies", "news", "playlists"] | None = None,
        fetch_favorites: bool = False,
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []
        if endpoint is None:
            endpoint = "art"

        tagname = self.format_tagname(tagname)

        last_art_pieces = None
        params = {
            "page": 1,
        }
        if fetch_favorites is True:
            url = self.ARTIST_PAGE_BASE_URL.format(tagname=tagname, sublink=f"favorites/{endpoint}")
        else:
            url = self.ARTIST_PAGE_BASE_URL.format(tagname=tagname, sublink=endpoint)

        while True:
            res = await self.request(url, params=params)
            if res.status_code == 302:
                return
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            art_pieces = soup.find_all(self.post_selector)

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

    # https://ARTIST.newgrounds.com/playlists Not planned


### artists
class _NewgroundsUserpostsAPI(_NewgroundsUserRootAPI):
    # https://ARTIST.newgrounds.com
    # https://ARTIST.newgrounds.com/art
    # https://ARTIST.newgrounds.com/audio
    # https://ARTIST.newgrounds.com/games
    # https://ARTIST.newgrounds.com/movies
    # https://ARTIST.newgrounds.com/news
    # playlists
    ME = "newgrounds"
    fetch_favorites = False


class NewgroundsArtAPI(_NewgroundsUserpostsAPI):
    # https://ARTIST.newgrounds.com/art
    ME = "newgrounds-artists"
    endpoint = "art"


### favs


class _NewgroundsUserfavoritesAPI(_NewgroundsUserRootAPI):
    ME = "newgrounds"
    fetch_favorites = True


class NewgroundsFavoriteArtAPI(_NewgroundsUserfavoritesAPI):
    # https://ARTIST.newgrounds.com/art
    ME = "newgrounds-favorites"
    endpoint = "art"


### tags


class _NewgroundsTagsRootAPI(NewgroundsRootAPI):
    TAG_PATTERN = r"https://(?:www\.)?newgrounds\.com.+(?:\&|\?)tags=([^/&\?=]+)"
    SPACE_REPLACE = "-"

    async def does_this_exist(self, tagname: str) -> bool:
        params: dict[str, str | int] = {
            "match": "tags",
            "tags": self.format_tagname(tagname),
            "sort": "date-desc",
            "page": 1,
        }
        url = self.TAG_PAGE_BASE_URL.format(sublink=self.endpoint)
        res = await self.request(url, params=params)
        return "<p>Nothing.</p>" not in res.text

    def _fetch_posts(
        self,
        tagname: str,
        update_ids: list[str] | None = None,
        ignore_contentfilters: bool = False,
    ) -> AsyncGenerator[scraper.PostData]:
        return self._unified_fetch_posts(
            tagname=tagname,
            update_ids=update_ids,
            ignore_contentfilters=ignore_contentfilters,
            endpoint=self.endpoint,
        )

    async def _unified_fetch_posts(
        self,
        tagname: str,
        update_ids: list[str] | None = None,
        ignore_contentfilters: bool = False,  # noqa: ARG002
        endpoint: Literal["art", "audio", "games", "movies", "news", "playlists"] | None = None,
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []
        if endpoint is None:
            endpoint = "art"

        tagname = self.format_tagname(tagname)

        params: dict[str, str | int] = {
            "match": "tags",
            "tags": tagname,
            "sort": "date-desc",
            "page": 1,
        }
        if not isinstance(params["page"], int):  # keep type checkers happy
            raise ValueError
        url = self.TAG_PAGE_BASE_URL.format(sublink=endpoint)

        first_page_art_pieces: Any = None
        while True:
            res = await self.request(url, params=params)
            if res.status_code == 302:
                return
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            art_pieces = soup.find_all(self.post_selector)

            if first_page_art_pieces is None:
                first_page_art_pieces = art_pieces
            else:
                if first_page_art_pieces == art_pieces:
                    return

            # For each found image, yield
            for art_piece in art_pieces:
                post_url = str(art_piece["href"])
                post_data = await self._get_post_data(post_url=post_url)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            params["page"] += 1


class NewgroundsTagsArtAPI(_NewgroundsTagsRootAPI):
    URL_TAG = "https://www.newgrounds.com/search/conduct/art?match=tags&tags={tagname}&sort=date-desc"
    ME = "newgrounds-tags"
    endpoint = "art"
