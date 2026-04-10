import asyncio

import easygui

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
from pythonripper.extractor import reddit


async def main(config: cfg.Config) -> None:
    dpath = config._downloaded_path()
    reply = easygui.textbox(msg="Please enter reddit posts you want to download:", title="Paste links...")
    if not reply:
        return
    urls = reply.split("\n")

    config = cfg.Config()

    obj = reddit.RedditAPI(config)

    for i, url in enumerate(urls):
        while len(url) > 0 and url[-1] == "/":
            url = f"{url[0:-1]}"
        if any(test == url for test in ("about:newtab", "about:home", "")):
            continue
        print(f"{i+1} / {len(urls)} - {url}")

        success = await obj.download_post(url=url, dpath=dpath)
        print(success, type(success))
        print("=" * 20)

    for folder in f.iter_directories(dpath):
        if not f.is_dir_empty(folder):
            folder.rmdir()


if __name__ == "__main__":
    configure = cfg.Config()
    cf.init_logger(configure, "error", False)
    asyncio.run(main(config=configure))
