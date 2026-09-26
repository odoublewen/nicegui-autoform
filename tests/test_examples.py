"""The shipped examples must actually render and submit.

Each example registers its page at import time and then calls ``ui.run()``,
which is stubbed out here so the module can be imported into the simulated
client instead of starting a server.
"""

from __future__ import annotations

import asyncio
import runpy
from pathlib import Path
from unittest import mock

import pytest
from nicegui import ui
from nicegui.testing import User

pytestmark = pytest.mark.asyncio

EXAMPLES = ["cyclopts_demo", "click_demo", "typer_demo", "argparse_demo"]
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def load(name: str) -> dict:
    with mock.patch("nicegui.ui.run"):
        return runpy.run_path(str(EXAMPLES_DIR / f"{name}.py"), run_name="__not_main__")


@pytest.mark.parametrize("name", EXAMPLES)
async def test_example_renders_its_form(user: User, name: str) -> None:
    load(name)
    await user.open("/")
    await user.should_see("Epochs")
    await user.should_see("Submit")
    await user.should_see(kind=ui.upload)  # the required Path field


@pytest.mark.parametrize("name", EXAMPLES)
async def test_example_reports_the_missing_required_path(user: User, name: str) -> None:
    load(name)
    await user.open("/")
    user.find("Submit").click()
    await asyncio.sleep(0.05)
    await user.should_see("1 field needs attention")


@pytest.mark.parametrize("name", EXAMPLES)
async def test_example_accepts_the_bundled_sample_file(user: User, name: str) -> None:
    """The sample input the examples tell you to upload must actually work."""
    sample = EXAMPLES_DIR / "data" / "measurements.csv"
    load(name)
    await user.open("/")

    upload = user.find(kind=ui.upload).elements.pop()
    await upload.handle_uploads(
        [ui.upload.SmallFileUpload(sample.name, "text/csv", sample.read_bytes())]
    )
    user.find("Submit").click()
    await asyncio.sleep(0.2)

    await user.should_not_see("1 field needs attention")
    # "13 lines" can only come from the callback having read the uploaded file:
    # the header plus 12 data rows of measurements.csv.
    await user.should_see("measurements.csv")
    await user.should_see("13 lines")
