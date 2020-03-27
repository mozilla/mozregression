import pytest

from mozregression import __version__
from mozregui.check_release import CheckRelease, QLabel, QUrl
from mozregui.main import MainWindow


@pytest.yield_fixture
def mainwindow(qtbot):
    main = MainWindow()
    qtbot.addWidget(main)
    yield main
    main.clear()


def test_check_release(qtbot, mocker, mainwindow):
    retry_get = mocker.patch("mozregui.check_release.retry_get")
    retry_get.return_value = mocker.Mock(json=lambda *a: {"tag_name": "0.0", "html_url": "url"})
    status_bar = mainwindow.ui.status_bar
    assert status_bar.findChild(QLabel, "") is None

    checker = CheckRelease(mainwindow)
    with qtbot.waitSignal(checker.thread.finished, raising=True):
        checker.check()

    lbl = status_bar.findChild(QLabel, "")
    assert lbl
    assert "There is a new release available!" in str(lbl.text())
    assert "0.0" in str(lbl.text())

    # simulate click on the link
    open_url = mocker.patch("mozregui.check_release.QDesktopServices.openUrl")
    checker.label_clicked("http://url")

    open_url.assert_called_once_with(QUrl("http://url"))
    assert not lbl.isVisible()


def test_check_release_no_update(qtbot, mocker, mainwindow):
    retry_get = mocker.patch("mozregui.check_release.retry_get")
    retry_get.return_value = mocker.Mock(
        json=lambda *a: {"tag_name": __version__, "html_url": "url"}
    )
    status_bar = mainwindow.ui.status_bar
    assert status_bar.findChild(QLabel, "") is None

    checker = CheckRelease(mainwindow)
    with qtbot.waitSignal(checker.thread.finished, raising=True):
        checker.check()

    assert status_bar.findChild(QLabel, "") is None
