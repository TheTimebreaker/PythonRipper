import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.subscription_management as sm


def main(config: cfg.Config) -> None:
    inp = input("Do you want to search the new websites' entries to <artist> or <tag>? Please enter either EXACTLY to choose: ")
    obj: sm.CombinedFile
    if inp in ("artist", "<artist>", "artists", "<artists>"):
        obj = sm.CombinedArtistFile(config)
        func = add_artists
    elif inp in ("tag", "<tag>", "tags", "<tags>"):
        obj = sm.CombinedBooruFile(config)
        func = add_tag
    else:
        print("No valid choice detected, run again.")
        return

    lookup = {}
    s = []
    for i, website in enumerate(obj.websites):
        lookup[i] = website
        s.append(f"({i}) {website}")
    print(" | ".join(s))
    inp2 = int(input("Enter a number to choose that website: "))
    if inp2 not in lookup:
        print("No valid choice detected, run again.")
        return

    inp3 = str(input("Do you want to AUTO-SKIP an entry, if the code cannot find any existing tags for any website? y(es) / n(o)): ")).lower()
    if inp3 in ("yes", "y"):
        skip_empty = True
    elif inp3 in ("no", "n"):
        skip_empty = False
    else:
        print("No valid choice detected, run again.")
        return

    choice = lookup[inp2]
    asyncio.run(func(obj, choice, skip_empty))


async def add_artists(obj: sm.CombinedFile, choice: str, skip_empty: bool) -> None:
    await obj.add_website(choice, skip_empty)


async def add_tag(obj: sm.CombinedFile, choice: str, skip_empty: bool) -> None:
    await obj.add_website(choice, skip_empty)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", False)
    main(config)
