from mozregui.wizard import BisectionWizard


def test_wizard(qtbot):
    # TODO
    wizard = BisectionWizard()
    qtbot.addWidget(wizard)
