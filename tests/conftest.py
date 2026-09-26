"""Shared pytest configuration.

``nicegui.testing.user_plugin`` provides the ``user`` fixture used by
``test_form.py``: a pure-Python simulated client, so the UI tests need no
browser. The broader ``nicegui.testing.plugin`` is deliberately avoided -- it
imports selenium for its ``screen`` fixture, which we do not use.
"""

pytest_plugins = ["nicegui.testing.user_plugin"]
