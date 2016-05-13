import asyncio
import websockets
import json


class TestCaseServer:
    """
    The websocket test case server that handles the submission of various
    websocket packets in order to test CB
    """

    def __init__(self, port="2220"):
        self.port = port    # Set the default chat port

    def run(self, test_cases):
        """
        Run the test-case server with supplied TestCaseTemplates
        """
        pass


class TestCaseTemplate:
    """
    The individual test case that TestCaseServer utilizes to test CB
    """

    def __init__(self, expected, submit=None local=False):
        self.submit_json = json.loads(submit)
        self.expected_json = json.loads(expected)
        self.local = False
