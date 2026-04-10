import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.subscription_management as sm


def main(config: cfg.Config) -> None:
    print("=" * 20)
    print("Artist file")

    _obj = sm.CombinedArtistFile(config)

    print("=" * 20)
    print("Booru file")

    _obj2 = sm.CombinedBooruFile(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", False)
    main(config)
