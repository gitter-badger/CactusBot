from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Session, relationship
from sqlalchemy.ext.declarative import declarative_base

from inspect import getfullargspec as get_full_arg_spec

from functools import wraps, partial

from os.path import abspath, dirname, join
from datetime import datetime

from re import sub, findall, match
from random import randrange, choice

from tornado.ioloop import PeriodicCallback

basedir = abspath(dirname(__file__))
engine = create_engine("sqlite:///" + join(basedir, "data/data.db"))
Base = declarative_base()

session = Session(engine)


def role_specific(*roles, reply=None):
    roles += ("Owner",)

    def role_specific_decorator(function):
        @wraps(function)
        def wrapper(self, args, data, **kwargs):
            if any(filter(lambda role: role in data["user_roles"], roles)):
                return function(self, args, data, **kwargs)
            representation = (
                reply if reply
                else roles[0].lower().replace(' ', '-') if roles
                else "permission"
            )
            return "This command is {}-only!".format(representation)
        return wrapper
    return role_specific_decorator

all_roles = (
    "Founder", "Staff", "Global Mod", "Mod", "Subscriber", "Pro", "User"
)

mod_roles = ("Founder", "Staff", "Global Mod", "Mod")
mod_only = role_specific(*mod_roles, reply="mod")


def subcommand(function):
    @wraps(function)
    def wrapper(self, args, data):
        kwargs = dict()  # TODO: typed arguments, TODO: arg regex

        arg_spec = get_full_arg_spec(function)
        arg_spec.args.pop(0)

        for argument, annotation in arg_spec.annotations.items():
            data_value = data.get(annotation)
            if isinstance(data_value, str):
                kwargs[argument] = data_value
            arg_spec.args.remove(argument)

        arg_len = len(arg_spec.args) + 1

        if len(args) - 1 < arg_len:
            return subcommand.__doc__ or "Not enough arguments!"

        if not arg_spec.args:
            return function(self)

        if arg_spec.annotations.get(arg_spec.args[-1], True) is True:
            args[arg_len:] = [' '.join(args[arg_len:])]

        kwargs.update(dict(zip(arg_spec.args, args[2: arg_len + 1])))

        return function(self, **kwargs)

    wrapper.is_subcommand = True
    wrapper.__name__ = function.__name__

    return wrapper


class CommandMeta(type):

    def __new__(cls, name, bases, attrs):
        subcommands = {}
        for value in attrs.values():
            if getattr(value, "is_subcommand", None):
                subcommands[value.__name__] = value
        attrs["subcommands"] = subcommands
        return super(CommandMeta, cls).__new__(cls, name, bases, attrs)


class NewCommand(metaclass=CommandMeta):  # TODO: rename class

    def __call__(self, args, data):
        if len(args) > 1:
            if args[1] in self.subcommands:
                return self.subcommands[args[1]](self, args, data)
            return "Invalid argument: '{}'.".format(args[1])
        return self.__doc__ or "Not enough arguments!"


class Command(Base):
    __tablename__ = "commands"

    id = Column(Integer, unique=True, primary_key=True)

    command = Column(String, unique=True)
    response = Column(String)

    calls = Column(Integer, default=0)

    creation = Column(DateTime)
    author = Column(Integer)

    permissions = Column(String)

    repeat = relationship("Repeat", backref="command")

    def __call__(self, args, data, **kwargs):
        if self.permissions:
            roles = str(self.permissions).split(',') + list(mod_roles)
        else:
            roles = all_roles

        @role_specific(*roles)
        def run_command(self, args, data, channel_name=None):
            response = self.response

            response = response.replace("%name%", data["user_name"])

            try:
                response = sub(
                    "%arg(\d+)%",
                    lambda match: args[int(match.group(1))],
                    response
                )
            except IndexError:
                return "Not enough arguments!"

            response = response.replace("%args%", ' '.join(args[1:]))

            self.calls += 1
            session.commit()

            response = response.replace("%count%", str(self.calls))

            response = response.replace(
                "%channel%",
                channel_name if channel_name else data["id"]
            )

            return response.split('\\n', 2)

        return run_command(self, args, data, **kwargs)


class Repeat(Base):
    __tablename__ = "repeating"

    id = Column(Integer, unique=True, primary_key=True)

    command_object = relationship("Command", backref="command_object")
    command_name = Column(String, ForeignKey("commands.command"))

    arguments = Column(String)

    interval = Column(Integer)


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, unique=True, primary_key=True)

    quote = Column(String)

    creation = Column(DateTime)
    author = Column(Integer)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, unique=True, primary_key=True)

    friend = Column(Boolean, default=False)

    joins = Column(Integer, default=0)
    messages = Column(Integer, default=0)
    offenses = Column(Integer, default=0)

    points = Column(Integer, default=0)


class CommandCommand(NewCommand):
    """Interact with command storage."""

    @mod_only
    @subcommand
    def add(self, command, response, user_id: "user_id"):
        """Add a command."""

        role_conversions = {
            '+': "Mod",
            '$': "Subscriber"
        }

        symbols, name = match(
            "^([{}]?)(.+)$".format(''.join(role_conversions)), command
        ).groups()

        permissions = ','.join(
            {role_conversions[symbol] for symbol in symbols})

        command = session.query(Command).filter_by(command=name).first()

        if command:
            command.permissions = permissions
            command.response = response
            command.author = user_id
        else:
            command = Command(
                command=name,
                permissions=permissions,
                response=response,
                creation=datetime.utcnow(),
                author=user_id
            )

        session.add(command)
        session.commit()
        return "Added command !{}.".format(name)

    @mod_only
    @subcommand
    def remove(self, command):
        command_row = session.query(Command).filter_by(command=command).first()
        if command_row is not None:
            session.delete(command_row)
            session.commit()
            return "Removed command !{}.".format(command_row.command)
        return "Command !{} does not exist!".format(command)

    @mod_only
    @subcommand
    def list(self):
        commands = session.query(Command).all()
        commands_list = ', '.join([c.command for c in commands if c.command])
        if commands_list:
            return "Commands: {commands}.".format(commands=commands_list)
        return "No commands added."


class QuoteCommand(Command):

    @mod_only
    def __call__(self, args, data):
        if len(args) > 1:
            try:
                id = int(args[1])
                return session.query(Quote).filter_by(id=id).first().quote
            except ValueError:
                pass
            except AttributeError:
                return "Undefined quote with ID {}.".format(id)

            if len(args) > 2:
                if args[1] == "add":
                    quote = Quote(
                        quote=' '.join(args[2:]),
                        creation=datetime.utcnow(),
                        author=data["user_id"]
                    )
                    session.add(quote)
                    session.flush()
                    session.commit()
                    return "Added quote with ID {}.".format(quote.id)
                elif args[1] == "remove":
                    try:
                        id = int(args[2])
                    except ValueError:
                        return "Invalid quote ID '{}'.".format(args[2])
                    quote = session.query(Quote).filter_by(id=id).first()
                    if quote is not None:
                        session.delete(quote)
                        session.commit()
                        return "Removed quote with ID {}.".format(args[2])
                    return "Quote {} does not exist!".format(args[2])
                return "Invalid argument: '{}'.".format(args[1])
            return "Not enough arguments."
        else:
            if not session.query(Quote).count():
                return "No quotes added."
            random_id = randrange(0, session.query(Quote).count())
            return session.query(Quote)[random_id].quote


class SocialCommand(Command):

    def __init__(self, get_channel):
        super(SocialCommand, self).__init__()
        self.get_channel = get_channel

    def __call__(self, args, data=None):
        channel_data = self.get_channel(data["channel"])
        name = channel_data["token"]
        s = channel_data["user"]["social"]
        a = {arg.lower() for arg in args[1:]}
        if s:
            if not a:
                return ', '.join(': '.join((k.title(), s[k])) for k in s)
            elif a.issubset(set(s).union({"beam"})):
                s.update({"beam": "https://beam.pro/{}".format(name)})
                return ', '.join(': '.join((k.title(), s[k])) for k in a)
            return "Data not found for service{s}: {}.".format(
                ', '.join(a - set(s)), s='s' * (len(a - set(s)) != 1))
        return "No social services were found on the streamer's profile."


class CubeCommand(Command):

    def __call__(self, args, data=None, **kwargs):
        if args[1] == '2' and len(args) == 2:
            return "8! Whoa, that's 2Cubed!"

        numbers = findall(
            "( [0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)",
            ' ' + ' '.join(args[1:]) + ' '
        )

        if len(numbers) == 0:
            return "{w[0]}{response}{w[1]}³".format(
                response=' '.join(args[1:]),
                w='  ' if findall(":\w+$", ' '.join(args[1:])) else '()'
            )
        elif len(numbers) > 8:
            return "Whoa! That's 2 many cubes!"

        return sub(
            "( [0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)",
            lambda match: " {:g} ".format(float(match.groups()[0]) ** 3),
            ' ' + ' '.join(args[1:]) + ' '
        )


class UptimeCommand(Command):

    def __init__(self, request):
        super(UptimeCommand, self).__init__()
        self.request = request

    def __call__(self, args, data):
        response = self.request(
            "/channels/{id}/manifest.light".format(id=data["channel"]))
        if response.get("since") is not None:
            return "Channel has been live for {}.".format(
                match(
                    "(.+)\.\d{6}",
                    str(datetime.utcnow() - datetime.strptime(
                        response["since"][:-5], "%Y-%m-%dT%H:%M:%S")
                        )).group(1))
        return "Channel is offline."


class PointsCommand(Command):

    def __init__(self, points_name):
        super(PointsCommand, self).__init__()
        self.points_name = points_name

    def __call__(self, args, data):
        if len(args) > 1:
            return "Points update in development. :cactus"
        user = session.query(User).filter_by(id=data["user_id"]).first()
        return "@{user} has {amount} {name}.".format(
            user=data["user_name"],
            amount=user.points,
            name=self.points_name + ('s' if user.points != 1 else ''))


class RepeatCommand(Command):

    def __init__(self, send_message, bot_name, channel):
        super(RepeatCommand, self).__init__()
        self.send_message = send_message
        self.data = {"user_name": bot_name, "user_roles": all_roles}
        self.channel = channel

        self.repeats = dict()

        for repeat in session.query(Repeat).all():
            periodic_callback = PeriodicCallback(
                partial(self.send, repeat),
                repeat.interval * 1000
            )
            self.repeats[repeat.command.command] = periodic_callback
            periodic_callback.start()

    @mod_only
    def __call__(self, args, data):
        if args[1] == "add":
            if len(args) > 3:
                try:
                    interval = int(args[2])
                except ValueError:
                    return "Invalid interval: '{}'.".format(args[2])

                repeat = session.query(Repeat).filter_by(
                    command_name=args[3]).first()

                if repeat:
                    repeat.interval = interval
                    repeat.arguments = ' '.join(args[3:])
                    periodic_callback = self.repeats[repeat.command.command]
                    periodic_callback.callback_time = interval * 1000
                    periodic_callback.stop()
                    periodic_callback.start()
                    session.add(repeat)
                    session.commit()
                    return "Repeat updated."

                command = session.query(Command).filter_by(command=args[3])
                if command.first():
                    command = command.first()
                    repeat = Repeat(
                        command_object=command,
                        interval=interval,
                        arguments=' '.join(args[3:])
                    )

                    periodic_callback = PeriodicCallback(
                        partial(self.send, repeat),
                        interval * 1000
                    )
                    self.repeats[args[3]] = periodic_callback
                    periodic_callback.start()
                    session.add(repeat)
                    session.commit()
                    return "Repeating command '!{}' every {} seconds.".format(
                        command.command, interval)
                return "Undefined command '!{}'.".format(args[3])
            return "Not enough arguments!"
        elif args[1] == "remove":
            if len(args) > 2:
                repeat = session.query(Repeat).filter_by(
                    command_name=args[2]).first()
                if repeat is not None:
                    self.repeats[args[2]].stop()
                    del self.repeats[args[2]]
                    session.delete(repeat)
                    session.commit()
                    return "Removed repeat for command !{}.".format(args[2])
                return "Repeat for !{} does not exist!".format(args[2])
            return "Not enough arguments!"
        elif args[1] == "list":
            repeats = session.query(Repeat).all()
            return "Repeats: {repeats}".format(
                repeats=', '.join(
                    [r.command.command + ' ' +
                        str(r.interval) for r in repeats]
                )
            )
        return "Invalid argument: {}.".format(args[1])

    def send(self, repeat):
        try:
            self.send_message(
                repeat.command(
                    repeat.arguments.split(),
                    self.data,
                    channel_name=self.channel
                )
            )
        except TypeError:
            command_name = repeat.command_name
            self.repeats[command_name].stop()
            del self.repeats[command_name]
            session.delete(repeat)
            session.commit()


class TemmieCommand(Command):
    quotes = [
        "fhsdhjfdsfjsddshjfsd",
        "hOI!!!!!! i'm tEMMIE!!",
        "awwAwa cute!! (pets u)",
        "OMG!! humans TOO CUTE (dies)",
        "NO!!!!! muscles r... NOT CUTE",
        "NO!!! so hungr... (dies)",
        "FOOB!!!",
        "can't blame a BARK for tryin'..."
    ]

    def __call__(self, args=None, data=None):
        return choice(self.quotes)


class FriendCommand(Command):

    def __init__(self, get_channel):
        super(FriendCommand, self).__init__()
        self.get_channel = get_channel

    @mod_only
    def __call__(self, args, data):
        if len(args) == 2:
            id = self.get_channel(args[1])["user"]["id"]
            query = session.query(User).filter_by(id=id).first()
            if query:
                query.friend = not query.friend
                session.commit()
                return "{}ed @{} as a friend.".format(
                    ["Remov", "Add"][query.friend], args[1])
            else:
                return "User has not entered this channel."
        elif len(args) > 2:
            return "Too many arguments."
        else:
            return "Not enough arguments."


class SpamProtCommand(Command):

    def __init__(self, update_config):
        super(SpamProtCommand, self).__init__()
        self.update_config = update_config

    @mod_only
    def __call__(self, args, data=None):
        if len(args) >= 3:
            if args[1] == "length":
                if args[2].isdigit():
                    self.update_config(
                        "spam_protection.maximum_message_length",
                        int(args[2]))
                    return "Maximum message length set to {}.".format(
                        args[2])
                return "Invalid number: '{}'.".format(args[2])
            elif args[1] == "caps":
                if args[2].isdigit():
                    self.update_config(
                        "spam_protection.maximum_message_capitals",
                        int(args[2]))
                    return "Maximum capitals per message set to {}.".format(
                        args[2])
                return "Invalid number: '{}'.".format(args[2])
            elif args[1] == "emotes":
                if args[2].isdigit():
                    self.update_config(
                        "spam_protection.maximum_message_emotes",
                        int(args[2]))
                    return "Maximum emotes per message set to {}.".format(
                        args[2])
                return "Invalid number: '{}'.".format(args[2])
            elif args[1] == "links":
                if args[2].lower() in ("true", "false"):
                    links_allowed = args[2].lower() == "true"
                    self.update_config(
                        "spam_protection.allow_links",
                        links_allowed)
                    return "Links are now {dis}allowed.".format(
                        dis="dis" * (not links_allowed))
                return "Invalid true/false: '{}'.".format(args[2])
            return "Invalid argument: '{}'.".format(args[1])
        return "Not enough arguments."


class ProCommand(Command):

    @role_specific("Pro", reply="pro")
    def __call__(self, args=None, data=None):
        return "I'm such a Pro! B)"


class SubCommand(Command):

    @role_specific("Subscriber", reply="sub")
    def __call__(self, args=None, data=None):
        return "I'm a subscriber! :salute"
