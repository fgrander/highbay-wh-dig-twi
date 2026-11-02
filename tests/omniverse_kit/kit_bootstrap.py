"""Runs inside Kit: starts a test script, so that even a failed import ends Kit with a report."""

import json
import os
import runpy
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(os.environ["HIGHBAY_KIT_SCRIPT"])))

try:
    runpy.run_path(os.environ["HIGHBAY_KIT_SCRIPT"], run_name="__main__")
except BaseException:
    with open(os.environ["HIGHBAY_KIT_ARGUMENTS"], encoding="utf-8") as file:
        results_file = json.load(file)["results_file"]
    with open(results_file, "w", encoding="utf-8") as file:
        json.dump({"script_error": traceback.format_exc()}, file)
    os._exit(0)
