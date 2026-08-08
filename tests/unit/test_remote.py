from __future__ import annotations

from unittest.mock import MagicMock

from alphacam_cli.gateway.remote import RemoteApplication, _DrawingProxy


def test_remote_new_drawing() -> None:
    session = MagicMock()
    session.new_drawing.return_value = {"geometries_count": 3}
    app = RemoteApplication(session)
    drw = app.new_drawing(200, 100, 5, "Hello")
    assert drw is not None
    assert isinstance(drw, _DrawingProxy)
    assert drw.geometries_count == 3
    session.new_drawing.assert_called_once_with(200, 100, 5, "Hello")


def test_remote_new_drawing_defaults() -> None:
    session = MagicMock()
    session.new_drawing.return_value = {"geometries_count": 0}
    app = RemoteApplication(session)
    drw = app.new_drawing()
    assert drw is not None
    session.new_drawing.assert_called_once_with(100, 50, 0, "")


def test_remote_new_drawing_none() -> None:
    session = MagicMock()
    session.new_drawing.return_value = None
    app = RemoteApplication(session)
    assert app.new_drawing() is None
