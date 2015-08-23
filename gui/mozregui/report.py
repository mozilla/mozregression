from PyQt4.QtGui import QTextBrowser, QTableView, QDesktopServices, QColor
from PyQt4.QtCore import QAbstractTableModel, QModelIndex, Qt,\
    pyqtSlot as Slot, pyqtSignal as Signal, QUrl

from mozregression.bisector import NightlyHandler

# Custom colors
GRAY_WHITE = QColor(243, 243, 243)
VERDICT_TO_ROW_COLORS = {
    "g": QColor(152, 251, 152),   # light green
    "b": QColor(250, 113, 113),  # light red
    "s": QColor(253, 248, 107),   # light yellow
    "r": QColor(225, 225, 225),   # light gray
}


class ReportItem(object):
    """
    A base item in the report view
    """
    def __init__(self):
        self.data = {}
        self.downloading = False
        self.progress = 0

    def update_pushlogurl(self, bisection):
        self.data['pushlog_url'] = bisection.handler.get_pushlog_url()

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
            self.build_type = "inbound"
        if self.build_type == 'nightly':
            self.first, self.last = handler.get_date_range()
        else:
            self.first, self.last = handler.get_range()
            self.first = self.first[:8]
            self.last = self.last[:8]
        if handler.find_fix:
            self.first, self.last = self.last, self.first

    def status_text(self):
        if 'pushlog_url' not in self.data:
            return ReportItem.status_text(self)
        return 'Started %s [%s - %s]' % (self.build_type,
                                         self.first, self.last)


class StepItem(ReportItem):
    """
    Report a bisection step
    """
    def __init__(self):
        ReportItem.__init__(self)
        self.state_text = 'Found'
        self.verdict = None

    def status_text(self):
        if not self.data:
            return ReportItem.status_text(self)
        if self.data['build_type'] == 'nightly':
            msg = "%%s nightly build: %s" % self.data['build_date']
        else:
            msg = "%%s inbound build: %s" % self.data['changeset'][:8]
        if self.verdict is not None:
            msg += ' (verdict: %s)' % self.verdict
        return msg % self.state_text


def _bulk_action_slots(action, slots, signal_object, slot_object):
    for name in slots:
        signal = getattr(signal_object, name)
        slot = getattr(slot_object, name)
        getattr(signal, action)(slot)


class ReportModel(QAbstractTableModel):
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.items = []
        self.bisector = None

    def clear(self):
        self.beginResetModel()
        self.items = []
        self.endResetModel()

    @Slot(object)
    def attach_bisector(self, bisector):
        bisector_slots = ('step_started',
                          'step_build_found',
                          'step_testing',
                          'step_finished',
                          'started',
                          'finished')
        downloader_slots = ('download_progress', )

        if self.bisector:
            _bulk_action_slots('disconnect',
                               bisector_slots,
                               self.bisector,
                               self)
            _bulk_action_slots('disconnect',
                               downloader_slots,
                               self.bisector.download_manager,
                               self)

        if bisector:
            _bulk_action_slots('connect',
                               bisector_slots,
                               bisector,
                               self)
            _bulk_action_slots('connect',
                               downloader_slots,
                               bisector.download_manager,
                               self)

        self.bisector = bisector

    @Slot(object, int, int)
    def download_progress(self, dl, current, total):
        item = self.items[-1]
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
                return VERDICT_TO_ROW_COLORS.get(
                    str(item.verdict),
                    GRAY_WHITE)
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
            # update the pushlog for the last step
            last_item.update_pushlogurl(bisection)
            self.update_item(last_item)
            # and add a new step
            self.append_item(StepItem())

    @Slot(object, int, object)
    def step_build_found(self, bisection, build_infos):
        last_item = self.items[-1]

        if isinstance(last_item, StartItem):
            # update the pushlog for the start step
            last_item.update_pushlogurl(bisection)
            self.update_item(last_item)

            # and add the new step with build_infos
            item = StepItem()
            item.state_text = 'Downloading'
            item.downloading = True
            item.data.update(build_infos.to_dict())
            self.append_item(item)
        else:
            # previous item is a step, just update it
            last_item.data.update(build_infos.to_dict())
            last_item.state_text = 'Downloading'
            last_item.downloading = True
            self.update_item(last_item)

    @Slot(object, int, object)
    def step_testing(self, bisection, build_infos):
        last_item = self.items[-1]
        last_item.downloading = False
        last_item.state_text = 'Testing'
        self.update_item(last_item)

    @Slot(object, int, str)
    def step_finished(self, bisection, verdict):
        # step finished, just store the verdict
        item = self.items[-1]
        item.state_text = 'Tested'
        item.verdict = verdict
        self.update_item(item)

    @Slot(object, int)
    def finished(self, bisection, result):
        # remove the last insterted step
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

    def clear(self):
        QTextBrowser.clear(self)
        self.setStyleSheet("background-color: white;")

    @Slot(object)
    def update_content(self, item):
        if not item.data:
            self.clear()
            return

        html = ""
        self.setStyleSheet("background-color:%s;" % GRAY_WHITE.name())
        for k in sorted(item.data):
            v = item.data[k]
            html += '<strong>%s</strong>: ' % k
            if isinstance(v, basestring):
                url = QUrl(v)
                if url.isValid() and url.scheme():
                    v = '<a href="%s">%s</a>' % (v, v)
            html += '%s<br>' % v
        self.setHtml(html)

    @Slot(QUrl)
    def on_anchor_clicked(self, url):
        QDesktopServices.openUrl(url)
