# CactusBot!

from logging import getLogger as get_logger
from logging import getLevelName as get_level_name
from logging import StreamHandler, FileHandler, Formatter

from .models import Base, engine

from json import load, dump

from os.path import exists
from shutil import copyfile

from functools import reduce, partial

from tornado.autoreload import add_reload_hook, watch, start

from sys import exit
from traceback import format_exc
from time import sleep


cactus_art = """CactusBot initialized!

      ,`""',
      ;' ` ;
      ;`,',;
      ;' ` ;
 ,,,  ;`,',;               _____           _
;,` ; ;' ` ;   ,',        / ____|         | |
;`,'; ;`,',;  ;,' ;      | |     __ _  ___| |_ _   _ ___
;',`; ;` ' ; ;`'`';      | |    / _` |/ __| __| | | / __|
;` '',''` `,',`',;       | |___| (_| | (__| |_| |_| \__ \\
 `''`'; ', ;`'`'          \_____\__,_|\___|\__|\__,_|___/
      ;' `';
      ;` ' ;
      ;' `';
      ;` ' ;
      ; ',';
      ;,' ';

Made by: 2Cubed, Innectic, and ParadigmShift3d
"""


class Cactus:
    started = False
    connected = False

    def __init__(self, service, handler, **kwargs):

        self.handler = handler
        self.service = service

        self.debug = kwargs.get("debug", False)

        self.config_file = kwargs.get("config_file", "data/config.json")
        self.stats_file = kwargs.get("stats_file", "data/stats.json")
        self.database = kwargs.get("database", "data/data.db")

        self.silent = kwargs.get("silent", False)
        self.no_messages = kwargs.get("no_messages", False)

        self.logger = kwargs.get("logger") or self._init_logger(
            self.debug, kwargs.get("log_to_file", True))

        self._init_database(self.database)

    def _init_logger(self, level="INFO", file_logging=True, **kwargs):
        """Initialize logger."""

        self.logger = get_logger(__name__)
        self.logger.propagate = False

        self.logger.setLevel("DEBUG")

        if str(level).lower() == "true":
            level = "DEBUG"
        elif str(level).lower() == "false":
            level = "WARNING"
        elif hasattr(level, "upper"):
            level = level.upper()

        format = kwargs.get(
            "format",
            "%(asctime)s %(name)s %(levelname)-8s %(message)s"
        )

        formatter = Formatter(format, datefmt='%Y-%m-%d %H:%M:%S')

        try:
            from coloredlogs import ColoredFormatter
            colored_formatter = ColoredFormatter(format)
        except ImportError:
            colored_formatter = formatter
            self.logger.warning(
                "Module 'coloredlogs' unavailable; using ugly logging.")

        stream_handler = StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(colored_formatter)
        self.logger.addHandler(stream_handler)

        if file_logging:  # TODO: Reimplement
            file_handler = FileHandler("latest.log")
            file_handler.setLevel("DEBUG")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        get_logger("requests").setLevel(get_level_name("WARNING"))

        self.logger.info("Logger initialized with level '{}'.".format(level))

        return self.logger

    def _init_database(self, database):
        """Ensure the database exists."""

        if exists(database):
            self.logger.info("Found database.")
        else:
            self.logger.info("Database wasn't found.")
            self.logger.info("Creating and setting defaults...")

            Base.metadata.create_all(engine)

            self.logger.info("Done!")

    def load_config(self, filename):
        """Load configuration file."""

        if exists(filename):
            self.logger.info("Configuration file found. Loading...")
            self.config_file = filename
            with open(filename) as config:
                self.config = load(config)
                return self.config
        else:
            self.logger.warn("Configuration file was not found. Creating...")
            copyfile("data/config-template.json", filename)
            self.logger.error(
                "Configuration file created. Please enter values and restart.")
            raise FileNotFoundError("Configuration file not found.")
            exit()

    def load_stats(self, filename):
        """Load statistics file."""

        self.logger.warning("Statistics are not yet implemented.")
        return dict()

        if exists(filename):
            self.stats_file = filename
            self.logger.info("Statistics file found. Loading...")
            with open(filename) as stats:
                self.stats = load(stats)
                return self.stats
        else:
            self.logger.warn("Statistics file not found. Creating...")
            copyfile("data/stats-template.json", "data/stats.json")
            self.logger.info("Statistics file created.")

    def update_config(self, keys, value):
        """Update configuration file value."""

        with open(self.config_file, 'r') as config:
            config_data = load(config)
            reduce(lambda d, k: d[k], keys.split('.')[:-1], config_data)[
                keys.split('.')[-1]] = value
        with open(self.config_file, 'w+') as config:
            dump(config_data, config, indent=2, sort_keys=True)
        self.config = config_data
        return self.config

    def update_stats(self, keys, value):
        """Update statistics file value."""

        self.logger.warning("Statistics are not yet implemented.")
        return

        with open(self.stats_file, 'r') as stats:
            stats_data = load(stats)
            reduce(lambda d, k: d[k], keys.split('.')[:-1], stats_data)[
                keys.split('.')[-1]] = value
        with open(self.stats_file, 'w+') as stats:
            dump(stats_data, stats, indent=2, sort_keys=True)
        self.stats = stats_data
        return self.stats

    def run(self, *args, **kwargs):
        """Run bot."""

        self.logger.info(cactus_art)
        self.load_config(filename=self.config_file)
        self.load_stats(filename=self.stats_file)

        while self.config.get("autorestart") or not self.started:
            try:
                self.bot_data = self.service.login(**self.config["auth"])
                self.logger.info("Authenticated as: {}.".format(
                    self.bot_data["username"]))

                self.started = True

                self.channel = self.config["channel"]
                self.channel_data = self.service.get_channel(self.channel)

                self.handler._init_commands()

                self.service.connect(
                    self.channel_data["id"],
                    self.bot_data["id"],
                    silent=self.silent)

                self.service.connect_to_liveloading(
                    self.channel_data["id"],
                    self.channel_data["userId"])

                if str(self.debug).lower() in ("true", "debug"):
                    add_reload_hook(partial(
                        self.send_message,
                        "Restarting, thanks to debug mode. :spaceship"
                    ))
                    watch(self.config_file)
                    start(check_time=5000)

                from tornado.ioloop import IOLoop  # TODO: Fix
                IOLoop.instance().start()

            except KeyboardInterrupt:
                print()
                self.logger.info("Removing thorns... done.")
                try:
                    self.send_message("CactusBot deactivated! :cactus")
                except Exception:
                    pass
                finally:
                    exit()

            except Exception:
                self.logger.critical("Oh no, I crashed!")

                try:
                    self.send_message("Oh no, I crashed! :127")
                except Exception:
                    pass

                self.logger.error('\n\n' + format_exc())

                if self.config.get("autorestart"):
                    self.logger.info("Restarting in 10 seconds...")
                    try:
                        sleep(10)
                    except KeyboardInterrupt:
                        self.logger.info("CactusBot deactivated.")
                        exit()
                else:
                    self.logger.info("CactusBot deactivated.")
                    exit()