import time

import pytest

from mozregui import log_report


@pytest.fixture
def log_view(qtbot):
    widget = log_report.LogView()
    qtbot.addWidget(widget)
    widget.log_model = log_report.LogModel()
    widget.log_model.log.connect(widget.on_log_received)
    widget.show()
    qtbot.waitForWindowShown(widget)
    return widget


def test_log_report_report_log_line(log_view):
    # view is first empty
    assert str(log_view.toPlainText()) == ""
    assert log_view.blockCount() == 1  # 1 for an empty document

    # send a log line
    log_view.log_model({"message": "my message", "level": "INFO", "time": time.time()})

    assert log_view.blockCount() == 2
    assert "INFO : my message" in str(log_view.toPlainText())


def test_log_report_report_no_more_than_1000_lines(log_view):
    for i in range(1001):
        log_view.log_model({"message": str(i), "level": "INFO", "time": time.time()})

    assert log_view.blockCount() == 1000
    lines = str(log_view.toPlainText()).splitlines()
    assert len(lines) == 999
    assert "INFO : 1000" in lines[-1]
    assert "INFO : 2" in lines[0]  # 2 first lines were dropped


def test_log_report_sets_correct_user_data(log_view):
    """Assumes that only the correct log levels are entered"""
    # Inserts a log message for each log user level
    for log_level in log_report.log_levels.keys():
        log_view.log_model(
            {"message": "%s message" % log_level, "level": "%s" % log_level, "time": time.time()}
        )
    # Checks each log level message to make sure the correct
    # user data is entered
    for current_block in log_view.text_blocks():
        for log_level in log_report.log_levels.keys():
            if log_level in current_block.text():
                assert current_block.userData().log_lvl == log_report.log_levels[log_level]


def test_log_report_filters_data_below_current_log_level(log_view):
    # Using the WARNING log level
    log_view.log_lvl = log_report.log_levels["WARNING"]
    current_log_level = log_view.log_lvl
    # Inserts a log message for each log user level
    for log_level in log_report.log_levels.keys():
        log_view.log_model(
            {"message": "%s message" % log_level, "level": "%s" % log_level, "time": time.time()}
        )
    # Check that log messages above the current log level are visible
    # and log messages below the log level are invisible
    for current_block in log_view.text_blocks():
        current_block_log_level = current_block.userData().log_lvl
        if current_log_level < current_block_log_level:
            assert current_block.isVisible() is False
        else:
            assert current_block.isVisible() is True
