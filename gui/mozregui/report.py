from PySide2.QtCore import QAbstractTableModel, QModelIndex, Qt, QUrl, Signal, Slot
from PySide2.QtGui import QColor, QDesktopServices
from PySide2.QtWidgets import QTableView, QTextBrowser

from mozregression.bisector import NightlyHandler

# Custom colors
GRAY_WHITE = QColor(243, 243, 243)
VERDICT_TO_ROW_COLORS = {
    "g": QColor(152, 251, 152),  # light green
    "b": QColor(250, 113, 113),  # light red
    "s": QColor(253, 248, 107),  # light yellow
    "r": QColor(225, 225, 225),  # light gray
}


class ReportItem(object):
    """
    A base item in the report view
    """

    def __init__(self):
        self.data = {}
        self.downloading = False
        self.waiting_evaluation = False
        self.progress = 0

    def update_pushlogurl(self, bisection):
        if bisection.handler.found_repo:
            self.data["pushlog_url"] = bisection.handler.get_pushlog_url()
        else:
            self.data["pushlog_url"] = "Not available"
        self.data["repo_name"] = bisection.build_range[0].repo_name

    def status_text(self):
        return "Looking for build data..."

    def set_progress(self, current, total):
        self.progress = (current * 100) / total


class StartItem(ReportItem):
    """
    Report a started bisection
    """

    def update_pushlogurl(self, bisection):
        ReportItem.update_pushlogurl(self, bisection)
        handler = bisection.handler
        if isinstance(handler, NightlyHandler):
            self.build_type = "nightly"
        else:
            self.build_type = "integration"
        if self.build_type == "nightly":
            self.first, self.last = handler.get_date_range()
        else:
            self.first, self.last = handler.get_range()
            self.first = self.first[:8]
            self.last = self.last[:8]
        if handler.find_fix:
            self.first, self.last = self.last, self.first

    def status_text(self):
        if "pushlog_url" not in self.data:
            return ReportItem.status_text(self)
        return "Bisecting on %s [%s - %s]" % (
            self.data["repo_name"],
            self.first,
            self.last,
        )


class StepItem(ReportItem):
    """
    Report a bisection step
    """

    def __init__(self):
        ReportItem.__init__(self)
        self.state_text = "Found"
        self.verdict = None

    def status_text(self):
        if not self.data:
            return ReportItem.status_text(self)
        if self.data["build_type"] == "nightly":
            desc = self.data["build_date"]
        else:
            desc = self.data["changeset"][:8]
        if self.verdict is not None:
            desc = "%s (verdict: %s)" % (desc, self.verdict)
        return "%s %s build: %s" % (self.state_text, self.data["repo_name"], desc)


def _bulk_action_slots(action, slots, signal_object, slot_object):
    for name in slots:
        signal = getattr(signal_object, name)
        slot = getattr(slot_object, name)
        getattr(signal, action)(slot)


class ReportModel(QAbstractTableModel):
    need_evaluate_editor = Signal(bool, QModelIndex)

    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.items = []
        self.bisector = None
        self.single_runner = None

    def clear(self):
        self.beginResetModel()
        self.items = []
        self.endResetModel()

    @Slot(object)
    def attach_bisector(self, bisector):
        bisector_slots = (
            "step_started",
            "step_build_found",
            "step_testing",
            "step_finished",
            "started",
            "finished",
        )
        downloader_slots = ("download_progress",)

        if bisector:
            self.attach_single_runner(None)
            _bulk_action_slots("connect", bisector_slots, bisector, self)
            _bulk_action_slots("connect", downloader_slots, bisector.download_manager, self)

        self.bisector = bisector

    @Slot(object)
    def attach_single_runner(self, single_runner):
        sr_slots = ("started", "step_build_found", "step_testing")
        downloader_slots = ("download_progress",)

        if single_runner:
            self.attach_bisector(None)
            _bulk_action_slots("connect", sr_slots, single_runner, self)
            _bulk_action_slots("connect", downloader_slots, single_runner.download_manager, self)

        self.single_runner = single_runner

    @Slot(object, int, int)
    def download_progress(self, dl, current, total):
        item = self.items[-1]
        item.state_text = "Downloading"
        item.downloading = True
        item.set_progress(current, total)
        self.update_item(item)

    def get_item(self, index):
        return self.items[index.row()]

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        item = self.items[index.row()]
        if role == Qt.DisplayRole:
            return item.status_text()
        elif role == Qt.BackgroundRole:
            if isinstance(item, StepItem) and item.verdict:
                return VERDICT_TO_ROW_COLORS.get(str(item.verdict), GRAY_WHITE)
            else:
                return GRAY_WHITE

        return None

    def update_item(self, item):
        index = self.createIndex(self.items.index(item), 0)
        self.dataChanged.emit(index, index)

    def append_item(self, item):
        row = self.rowCount()
        self.beginInsertRows(QModelIndex(), row, row)
        self.items.append(item)
        self.endInsertRows()

    @Slot()
    def started(self):
        # when a bisection starts, insert an item to report it
        self.append_item(StartItem())

    @Slot(object, int)
    def step_started(self, bisection):
        last_item = self.items[-1]
        if isinstance(last_item, StepItem):
            # update the pushlog for the start step
            if hasattr(bisection, "handler"):
                last_item.update_pushlogurl(bisection)
                self.update_item(last_item)
            # and add a new step
            self.append_item(StepItem())

    @Slot(object, int, object)
    def step_build_found(self, bisection, build_infos):
        last_item = self.items[-1]

        if isinstance(last_item, StartItem):
            # update the pushlog for the start step
            if hasattr(bisection, "handler"):
                last_item.update_pushlogurl(bisection)
                self.update_item(last_item)
            else:
                # single runner case
                # TODO: rework report.py implementation...
                self.finished(None, None)  # remove last item

            # and add the new step with build_infos
            item = StepItem()
            item.data.update(build_infos.to_dict())
            self.append_item(item)
        else:
            # previous item is a step, just update it
            last_item.data.update(build_infos.to_dict())
            self.update_item(last_item)

    @Slot(object, int, object)
    def step_testing(self, bisection, build_infos):
        last_item = self.items[-1]
        last_item.downloading = False
        last_item.waiting_evaluation = True
        last_item.state_text = "Testing"
        # we may have more build data now that the build has been installed
        last_item.data.update(build_infos.to_dict())
        if hasattr(bisection, "handler"):
            last_item.update_pushlogurl(bisection)

        self.update_item(last_item)
        if hasattr(bisection, "handler"):
            # not a single runner
            index = self.createIndex(self.rowCount() - 1, 0)
            self.need_evaluate_editor.emit(True, index)

    @Slot(object, int, str)
    def step_finished(self, bisection, verdict):
        # step finished, just store the verdict
        item = self.items[-1]
        item.waiting_evaluation = False
        item.state_text = "Tested"
        item.verdict = verdict
        self.update_item(item)
        if hasattr(bisection, "handler"):
            # not a single runner
            index = self.createIndex(self.rowCount() - 1, 0)
            self.need_evaluate_editor.emit(False, index)

    @Slot(object, int)
    def finished(self, bisection, result):
        # remove the last inserted step
        if not self.items[-1].data:
            index = len(self.items) - 1
            self.beginRemoveRows(QModelIndex(), index, index)
            self.items.pop(index)
            self.endRemoveRows()


class ReportView(QTableView):
    step_report_changed = Signal(object)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self._model = ReportModel()
        self.setModel(self._model)
        self._model.dataChanged.connect(self.on_item_changed)

    def currentChanged(self, current, previous):
        if current.row() >= 0:
            item = self._model.items[current.row()]
            self.step_report_changed.emit(item)

    @Slot(QModelIndex, QModelIndex)
    def on_item_changed(self, top_left, bottom_right):
        if self.currentIndex().row() == top_left.row():
            item = self._model.items[top_left.row()]
            # while an item is downloaded, the underlying data model
            # change a lot only to update the download progress state.
            # It becomes impossible then to scroll the
            # BuildInfoTextBrowser, so we do not want to update
            # that when we are downloading.
            if not item.downloading:
                self.step_report_changed.emit(item)


class BuildInfoTextBrowser(QTextBrowser):
    def __init__(self, parent=None):
        QTextBrowser.__init__(self, parent)
        self.anchorClicked.connect(self.on_anchor_clicked)

    @Slot(object)
    def update_content(self, item):
        if not item.data:
            self.clear()
            return

        html = u""
        for k in sorted(item.data):
            v = item.data[k]
            if v is not None:
                html += "<strong>%s</strong>: " % k
                if isinstance(v, str):
                    url = QUrl(v)
                    if url.isValid() and url.scheme():
                        v = '<a href="%s">%s</a>' % (v, v)
                html += "{}<br>".format(v)
        self.setHtml(html)

    @Slot(QUrl)
    def on_anchor_clicked(self, url):
        QDesktopServices.openUrl(url)
