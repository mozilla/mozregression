import pytest
import time

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
    assert str(log_view.toPlainText()) == ''
    assert log_view.blockCount() == 1  # 1 for an empty document

    # send a log line
    log_view.log_model({'message': 'my message', 'level': 'INFO',
                        'time': time.time()})

    assert log_view.blockCount() == 2
    assert 'INFO : my message' in str(log_view.toPlainText())


def test_log_report_report_no_more_than_1000_lines(log_view):
    for i in range(1001):
        log_view.log_model({'message': str(i), 'level': 'INFO',
                            'time': time.time()})

    assert log_view.blockCount() == 1000
    lines = str(log_view.toPlainText()).splitlines()
    assert len(lines) == 999
    assert 'INFO : 1000' in lines[-1]
    assert 'INFO : 2' in lines[0]  # 2 first lines were dropped
