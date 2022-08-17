import pytest
from PySide2.QtCore import QDate

from mozregression.fetch_configs import CommonConfig
from mozregui.wizard import (
    BisectionWizard,
    BuildSelectionPage,
    IntroPage,
    ProfilePage,
    SingleBuildSelectionPage,
    SingleRunWizard,
)

PAGES_BISECTION_WIZARD = (IntroPage, ProfilePage, BuildSelectionPage)
PAGES_SINGLE_RUN_WIZARD = (IntroPage, ProfilePage, SingleBuildSelectionPage)


@pytest.mark.parametrize(
    "os, bits, wizard_class, pages",
    [
        (
            "linux",
            64,
            BisectionWizard,
            PAGES_BISECTION_WIZARD,
        ),
        ("win", 32, BisectionWizard, PAGES_BISECTION_WIZARD),
        ("mac", 64, BisectionWizard, PAGES_BISECTION_WIZARD),
        ("linux", 64, SingleRunWizard, PAGES_SINGLE_RUN_WIZARD),
        ("win", 32, SingleRunWizard, PAGES_SINGLE_RUN_WIZARD),
        ("mac", 64, SingleRunWizard, PAGES_SINGLE_RUN_WIZARD),
    ],
)
def test_wizard(mocker, qtbot, os, bits, wizard_class, pages):
    mozinfo = mocker.patch("mozregui.wizard.mozinfo")
    mozinfo.os = os
    mozinfo.bits = bits

    wizard = wizard_class()
    qtbot.addWidget(wizard)
    wizard.show()
    qtbot.waitForWindowShown(wizard)

    for page_class in pages:
        assert isinstance(wizard.currentPage(), page_class)
        wizard.next()

    # everything has been visited
    assert wizard.visitedPages() == wizard.pageIds()

    fetch_config, options = wizard.options()

    now = QDate.currentDate()

    assert isinstance(fetch_config, CommonConfig)
    assert fetch_config.app_name == "firefox"  # this is the default
    assert fetch_config.os == os
    assert fetch_config.bits == bits
    assert fetch_config.build_type == "shippable"
    assert not fetch_config.repo

    assert options["profile"] == ""
    if isinstance(wizard, SingleRunWizard):
        assert options["launch"] == now.addDays(-3).toPython()
    else:
        assert options["good"] == now.addYears(-1).toPython()
        assert options["bad"] == now.toPython()
