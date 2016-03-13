from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base

from functools import wraps

from os.path import abspath, dirname, join
from datetime import datetime
from re import sub, findall
from random import randrange, choice
from uuid import uuid1

from beam import Beam

basedir = abspath(dirname(__file__))
engine = create_engine('sqlite:///' + join(basedir, 'data/data.db'))
Base = declarative_base()

session = Session(engine)


def role_specific(*roles, reply=None):
    roles += ("Owner",)

    def role_specific_decorator(function):
        @wraps(function)
        def wrapper(self, args, data):
            if any(filter(lambda r: r in data["user_roles"], roles)):
                return function(self, args, data)
            r = reply if reply else roles[0].lower() if roles else "permission"
            return "This command is {}-only!".format(r)
        return wrapper
    return role_specific_decorator

mod_only = role_specific("Founder", "Staff", "Global Mod", "Mod", reply="mod")


class StoredCommand(Base):
    __tablename__ = "commands"

    id = Column(Integer, unique=True, primary_key=True)

    command = Column(String, unique=True)
    response = Column(String)

    calls = Column(Integer, default=0)

    creation = Column(DateTime)
    author = Column(Integer)


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
    strikes = Column(Integer, default=0)

    points = Column(Integer, default=0)


class Command(StoredCommand):
    user = Beam()

    def __call__(self, user, *args, **kwargs):
        response = self.response

        response = response.replace("%name%", data["user_name"])

        try:
            response = sub(
                "%arg(\d+)%",
                lambda match: args[int(match.groups()[0])],
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

        return response


class CommandCommand(Command):
    @mod_only
    def __call__(self, args, data):
        if args[1] == "add":
            if len(args) > 3:
                q = session.query(Command).filter_by(command=args[2])
                if q.first():
                    q.first().response = ' '.join(args[3:])
                else:
                    c = Command(
                        command=args[2],
                        response=' '.join(args[3:]),
                        creation=datetime.utcnow(),
                        author=data["user_id"]
                    )
                    session.add(c)
                    session.commit()
                return "Added command !{}.".format(args[2])
            return "Not enough arguments!"
        elif args[1] == "remove":
            if len(args) > 2:
                q = session.query(Command).filter_by(command=args[2])
                if q.first():
                    q.delete()
                    session.commit()
                    return "Removed command !{}.".format(args[2])
                return "!{} does not exist!".format(args[2])
            return "Not enough arguments!"
        elif args[1] == "list":
            q = session.query(Command).all()
            return "Commands: {commands}".format(
                commands=', '.join([c.command for c in q if c.command]))
        return "Invalid argument: {}.".format(args[1])


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
                    q = Quote(
                        quote=' '.join(args[2:]),
                        creation=datetime.utcnow(),
                        author=data["user_id"]
                    )
                    session.add(q)
                    session.flush()
                    session.commit()
                    return "Added quote with ID {}.".format(q.id)
                elif args[1] == "remove":
                    try:
                        id = int(args[2])
                    except ValueError:
                        return "Invalid quote ID '{}'.".format(args[2])
                    q = session.query(Quote).filter_by(id=id)
                    if q.first():
                        q.delete()
                        session.commit()
                        return "Removed quote with ID {}.".format(args[2])
                    return "Quote {} does not exist!".format(args[2])
                return "Invalid argument: '{}'".format(args[1])
            return "Not enough arguments."
        else:
            if not session.query(Quote).count():
                return "No quotes added."
            random_id = randrange(0, session.query(Quote).count())
            return session.query(Quote)[random_id].quote


class SocialCommand(Command):
    def __call__(self, args, data=None):
        s = self.user.get_channel(data["channel"])["user"]["social"]
        a = [arg.lower() for arg in args[1:]]
        if s:
            if not a:
                return ', '.join(': '.join((k.title(), s[k])) for k in s)
            elif set(a).issubset(set(s)):
                return ', '.join(': '.join((k.title(), s[k])) for k in a)
            return "Data not found for service{s}: {}.".format(
                ', '.join(set(a)-set(s)), s='s'*(len(set(a)-set(s)) != 1))
        return "No social services were found on the streamer's profile."


class CubeCommand(Command):
    def __call__(self, args, data=None, **kwargs):
        if args[1] == '2' and len(args) == 2:
            return "8! Whoa, that's 2Cubed!"

        numbers = findall("\d+", ' '.join(args[1:]))

        if len(numbers) == 0:
            return "({})³".format(' '.join(args[1:]))
        elif len(numbers) > 8:
            return "Whoa! That's 2 many cubes!"

        nums = sub(
            "([0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?)",
            lambda match: "{:g}".format(float(match.groups()[0]) ** 3),
            ' '.join(args[1:])
        )
        return nums


class UptimeCommand(Command):
    def __call__(self, args, data=None):
        return "In development. :cactus"


class PointsCommand(Command):
    def __call__(self, args, data):
        q = session.query(User).filter_by(id=data["user_id"]).first()
        if q:
            q.points += 8
            session.commit()
            return str(q.points)
        else:
            u = User(id=data["user_id"])
            session.add(u)
            session.commit()
            return '0'


class ScheduleCommand(Command):
    session = Session

    def __init__(self, foo):
        self.foo = foo
        pass

    def __call__(self, args, data=None):
        """The way the command should work is: !schedule <INTERVAL> [MSG/!CMD]"""
        # If # of args is less than 4 (required minimum) ...
        if len(args) < 2:
            # ... then don't continue, return an error message
            # NOTE: Needs to return the proper usage
            return "INCORRECT ARGUMENTS (not enough arguing going on up in here!)"

        action = args[0]

        # Passed all of the parsing, begin the SQL stuffs
        # Parse data for add & edit separate from remove
        if action == "add" or action == "edit":
            if args[2].startswith("!"):
                type = "cmd"
            else:
                type = "msg"

            try:
                interval = int(args[1])
            except ValueError:
                return "INCORRECT ARGUMENTS (interval not int)"

            text = args[2]

        elif action == "remove":
            try:
                id = int(args[1])
            # Okay, it's not actually an int
            except ValueError:
                return "INCORRECT ARGUMENTS (ID not int)"

        else:
            # It's an unknown action
            # Return an error message
            return "INCORRECT ARGUMENTS (unknown action)"

        # Adding a new scheduled message
        if action == "add":
            return scheduled_add(text=text, interval=interval, type=type)

        # Remove a scheduled message
        elif action == "remove":
            return scheduled_remove(id=id)

        # Edit a scheduled message
        elif action == "edit":
            pass

# #### TO BE REDONE IN USERS MODEL #### #


class Points(Base):
    __tablename__ = "points"

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
    @mod_only
    def __call__(self, args, data):
        if len(args) == 2:
            id = self.user.get_channel(args[1])["user"]["id"]
            query = session.query(User).filter_by(id=id).first()
            if query:
                query.friend = not query.friend
                session.commit()
                return "{}ed {} as a friend.".format(
                    ["Remov", "Add"][query.friend], args[1])
            else:
                return "User has not entered this channel."
        elif len(args) > 2:
            return "Too many arguments."
        else:
            return "Not enough arguments."

    def remove_points(self, username, amount):
        query = session.query(Base).filter_by(username=username).first()

        if query:
            session.delete(query)
            return True
        return False


class SpamProtCommand(Command):
    def __init__(self, update_config):
        super(SpamProtCommand, self).__init__()
        self.update_config = update_config

    @mod_only
    def __call__(self, args, data=None):
        if len(args) >= 3:
            if args[1] == "length":
                self.update_config("spam_protection.maximum_message_length",
                                   int(args[2]))
                return "Maximum message length set to {}.".format(args[2])
            elif args[1] == "caps":
                self.update_config("spam_protection.maximum_message_capitals",
                                   int(args[2]))
                return "Maximum capitals per message set to {}.".format(
                    args[2])
            elif args[1] == "emotes":
                self.update_config("spam_protection.maximum_message_emotes",
                                   int(args[2]))
                return "Maximum emotes per message set to {}.".format(args[2])
            elif args[1] == "link":
                self.update_config("spam_protection.allow_links",
                                   bool(args[2]))
                return "Links are now {}allowed.".format("dis"*bool(args[2]))
        else:
            return "Not enough arguments"


class ProCommand(Command):
    @role_specific("Pro", reply="pro")
    def __call__(self, args=None, data=None):
        return "I'm such a Pro! B)"


class Schedule(Base):
    __tablename__ = "scheduled"

    id = Column(Integer, unique=True, primary_key=True)
    text = Column(String)
    interval = Column(Integer)
    last_ran = Column(Integer)
    uid = Column(String)
    type = Column(String)

class SubCommand(Command):
    @role_specific("Subscriber", reply="sub")
    def __call__(self, args=None, data=None):
        return "I'm a subscriber! :salute"
