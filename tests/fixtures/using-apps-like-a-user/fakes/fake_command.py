"""Stand-in for `open` and `osascript`: logs its arguments and does nothing else.

`FAKE_COMMAND_LOG` names the log and `FAKE_COMMAND_NAME` the tool being impersonated; a line
from `open` is how the fake orca learns that the app was "launched".
"""
import json
import os
import sys

with open(os.environ["FAKE_COMMAND_LOG"], "a") as handle:
    handle.write(json.dumps({"tool": os.environ["FAKE_COMMAND_NAME"], "argv": sys.argv[1:]}) + "\n")
