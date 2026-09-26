"""End-to-end form behaviour, driven through NiceGUI's simulated user."""

from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path

import cyclopts
import pytest
from nicegui import ui
from nicegui.testing import User

from nicegui_autoform import AutoForm, WidgetKind

pytestmark = pytest.mark.asyncio


@dataclass
class Config:
    """Config.

    Parameters
    ----------
    epochs: int
        number of epochs
    """

    epochs: int = 10
    lr: float = 0.001


def demo_app() -> cyclopts.App:
    app = cyclopts.App(name="demo")

    @app.command
    def train(name: str, epochs: int = 10, verbose: bool = False, mode: str = "fast"):
        """Train a model."""
        return {"name": name, "epochs": epochs, "verbose": verbose, "mode": mode}

    return app


def mount(build) -> list:
    """Render a form at ``/`` and return a list that collects submissions."""
    received: list = []

    @ui.page("/")
    def page() -> None:
        build(received)

    return received


async def wait_for(until=None, timeout: float = 2.0) -> None:
    """Give scheduled event handlers a turn to run.

    NiceGUI dispatches both clicks and uploads as tasks, so a test asserting on
    Python-side state has to yield to the loop. Polling ``until`` rather than
    sleeping a fixed interval keeps the tests both fast and non-flaky.
    """
    deadline = time.monotonic() + timeout
    while True:
        await asyncio.sleep(0.01)
        if until is None or until() or time.monotonic() > deadline:
            return


async def submit(user: User, until=None, timeout: float = 2.0) -> None:
    """Click Submit and let the handler finish."""
    user.find("Submit").click()
    await wait_for(until, timeout)


async def test_form_renders_labels_and_help(user: User) -> None:
    mount(lambda received: AutoForm(demo_app(), command="train"))
    await user.open("/")
    await user.should_see("Train a model.")
    await user.should_see("Name *")
    await user.should_see("Epochs")
    await user.should_see("Submit")


async def test_submitting_calls_the_commands_own_function(user: User) -> None:
    received = mount(
        lambda received: AutoForm(
            demo_app(), command="train", on_submit=lambda **kw: received.append(kw)
        )
    )
    await user.open("/")
    user.find("Name").type("alpha")
    user.find("Epochs").clear().type("25")
    await submit(user, until=lambda: received)
    assert received == [{"name": "alpha", "epochs": 25, "verbose": False, "mode": "fast"}]


async def test_defaults_are_used_for_untouched_fields(user: User) -> None:
    received = mount(
        lambda received: AutoForm(
            demo_app(), command="train", on_submit=lambda **kw: received.append(kw)
        )
    )
    await user.open("/")
    user.find("Name").type("alpha")
    await submit(user, until=lambda: received)
    assert received[0]["epochs"] == 10
    assert received[0]["mode"] == "fast"


async def test_a_missing_required_field_blocks_submission(user: User) -> None:
    received = mount(
        lambda received: AutoForm(
            demo_app(), command="train", on_submit=lambda **kw: received.append(kw)
        )
    )
    await user.open("/")
    await submit(user)
    await user.should_see("1 field needs attention")
    assert received == []


async def test_a_non_integer_blocks_an_int_field(user: User) -> None:
    received = mount(
        lambda received: AutoForm(
            demo_app(), command="train", on_submit=lambda **kw: received.append(kw)
        )
    )
    await user.open("/")
    user.find("Name").type("alpha")
    user.find("Epochs").clear().type("1.5")
    await submit(user)
    await user.should_see("1 field needs attention")
    assert received == []


async def test_initial_values_prefill_the_form(user: User) -> None:
    received = mount(
        lambda received: AutoForm(
            demo_app(),
            command="train",
            initial={"name": "preset", "epochs": 99},
            on_submit=lambda **kw: received.append(kw),
        )
    )
    await user.open("/")
    await submit(user, until=lambda: received)
    assert received[0]["name"] == "preset"
    assert received[0]["epochs"] == 99


async def test_excluded_fields_are_not_rendered(user: User) -> None:
    received = mount(
        lambda received: AutoForm(
            demo_app(),
            command="train",
            exclude=["mode"],
            initial={"mode": "slow"},
            on_submit=lambda **kw: received.append(kw),
        )
    )
    await user.open("/")
    await user.should_not_see("Mode")
    user.find("Name").type("alpha")
    await submit(user, until=lambda: received)
    assert received[0]["mode"] == "slow"


async def test_excluding_a_required_field_without_a_value_is_an_error() -> None:
    # Raised while resolving initial values, before any element is created.
    with pytest.raises(ValueError, match="hidden or excluded but has no default"):
        AutoForm(demo_app(), command="train", exclude=["name"])


async def test_an_async_on_submit_is_awaited(user: User) -> None:
    received: list = []

    async def handler(**kwargs) -> None:
        received.append(kwargs)

    @ui.page("/")
    def page() -> None:
        AutoForm(demo_app(), command="train", on_submit=handler)

    await user.open("/")
    user.find("Name").type("alpha")
    await submit(user, until=lambda: received)
    assert received[0]["name"] == "alpha"


async def test_a_raising_handler_is_reported_in_the_ui(user: User) -> None:
    def handler(**kwargs) -> None:
        raise RuntimeError("boom")

    @ui.page("/")
    def page() -> None:
        AutoForm(demo_app(), command="train", on_submit=handler)

    await user.open("/")
    user.find("Name").type("alpha")
    await submit(user)
    await user.should_see("Submission failed: boom")


async def test_a_nested_dataclass_renders_a_section_and_is_rebuilt(user: User) -> None:
    app = cyclopts.App(name="demo")
    received: list = []

    @app.command
    def train(config: Config, seed: int = 0):
        """Train."""

    @ui.page("/")
    def page() -> None:
        AutoForm(app, command="train", on_submit=lambda *a, **kw: received.append(kw))

    await user.open("/")
    await user.should_see("Config")  # the section heading
    user.find("Epochs").clear().type("7")
    await submit(user, until=lambda: received)
    assert received == [{"config": Config(epochs=7, lr=0.001), "seed": 0}]


async def test_widget_overrides_are_honoured(user: User) -> None:
    @ui.page("/")
    def page() -> None:
        AutoForm(demo_app(), command="train", widgets={"name": WidgetKind.TEXTAREA})

    await user.open("/")
    await user.should_see(kind=ui.textarea)


async def test_argparse_requires_on_submit() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--x", type=int, default=1)
    with pytest.raises(ValueError, match="on_submit is required"):
        AutoForm(parser)


async def test_argparse_handler_receives_a_namespace(user: User) -> None:
    received: list = []
    parser = argparse.ArgumentParser(prog="demo")
    parser.add_argument("--x", type=int, default=1)
    parser.add_argument("--verbose", action="store_true")

    @ui.page("/")
    def page() -> None:
        AutoForm(parser, on_submit=received.append)

    await user.open("/")
    user.find("X").clear().type("5")
    await submit(user, until=lambda: received)
    assert received == [argparse.Namespace(x=5, verbose=False)]


async def test_result_records_the_last_submission(user: User) -> None:
    forms: list[AutoForm] = []

    @ui.page("/")
    def page() -> None:
        forms.append(AutoForm(demo_app(), command="train", on_submit=lambda **kw: None))

    await user.open("/")
    user.find("Name").type("alpha")
    await submit(user, until=lambda: forms[0].result is not None)
    assert forms[0].result is not None
    _, kwargs = forms[0].result
    assert kwargs["name"] == "alpha"


async def test_a_path_field_renders_as_an_upload(user: User) -> None:
    app = cyclopts.App(name="demo")

    @app.command
    def train(data: Path): ...

    @ui.page("/")
    def page() -> None:
        AutoForm(app, command="train")

    await user.open("/")
    await user.should_see(kind=ui.upload)


async def test_an_uploaded_file_reaches_the_callback_as_a_path(user: User) -> None:
    """The upload handler spills the bytes to a temp file and passes its Path."""
    app = cyclopts.App(name="demo")
    received: list = []

    @app.command
    def train(data: Path, epochs: int = 10):
        """Train."""

    @ui.page("/")
    def page() -> None:
        AutoForm(app, command="train", on_submit=lambda **kw: received.append(kw))

    await user.open("/")
    upload = user.find(kind=ui.upload).elements.pop()
    await upload.handle_uploads([ui.upload.SmallFileUpload("data.csv", "text/csv", b"a,b\n1,2\n")])
    await submit(user, until=lambda: received)

    assert len(received) == 1
    path = received[0]["data"]
    assert isinstance(path, Path)
    assert path.name == "data.csv"  # the original name is preserved, not randomised
    assert path.read_bytes() == b"a,b\n1,2\n"


async def test_an_upload_satisfies_a_required_path_field(user: User) -> None:
    app = cyclopts.App(name="demo")

    @app.command
    def train(data: Path):
        """Train."""

    forms: list[AutoForm] = []

    @ui.page("/")
    def page() -> None:
        forms.append(AutoForm(app, command="train", on_submit=lambda **kw: None))

    await user.open("/")
    assert forms[0].errors() == {("data",): "This field is required"}
    upload = user.find(kind=ui.upload).elements.pop()
    await upload.handle_uploads([ui.upload.SmallFileUpload("d.txt", "text/plain", b"x")])
    await wait_for(until=lambda: not forms[0].errors())
    assert forms[0].errors() == {}


async def test_a_client_supplied_path_cannot_escape_the_temp_directory(user: User) -> None:
    """The uploaded filename comes from the client, so only its basename is used."""
    app = cyclopts.App(name="demo")
    received: list = []

    @app.command
    def train(data: Path):
        """Train."""

    @ui.page("/")
    def page() -> None:
        AutoForm(app, command="train", on_submit=lambda **kw: received.append(kw))

    await user.open("/")
    upload = user.find(kind=ui.upload).elements.pop()
    await upload.handle_uploads([ui.upload.SmallFileUpload("../../evil.conf", "text/plain", b"x")])
    await submit(user, until=lambda: received)

    path = received[0]["data"]
    assert path.name == "evil.conf"
    assert path.parent.name.startswith("nicegui-autoform-")
    assert ".." not in path.parts


async def test_each_upload_gets_its_own_directory(user: User) -> None:
    """Preserving real names is only safe because names cannot collide."""
    app = cyclopts.App(name="demo")

    @app.command
    def train(data: Path): ...

    forms: list[AutoForm] = []

    @ui.page("/")
    def page() -> None:
        forms.append(AutoForm(app, command="train", on_submit=lambda **kw: None))

    await user.open("/")
    upload = user.find(kind=ui.upload).elements.pop()
    await upload.handle_uploads([ui.upload.SmallFileUpload("d.csv", "text/csv", b"first")])
    await wait_for(until=lambda: forms[0].values.get("data") is not None)
    first = forms[0].values["data"]

    await upload.handle_uploads([ui.upload.SmallFileUpload("d.csv", "text/csv", b"second")])
    await wait_for(until=lambda: forms[0].values["data"] != first)
    second = forms[0].values["data"]

    assert first != second
    assert first.read_bytes() == b"first"  # the first upload was not clobbered
    assert second.read_bytes() == b"second"
