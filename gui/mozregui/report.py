from PyQt4.QtGui import QTextBrowser, QTableView, QDesktopServices
from PyQt4.QtCore import QAbstractTableModel, QModelIndex, Qt,\
    pyqtSlot as Slot, pyqtSignal as Signal, QUrl


class ReportItem(object):
    """
    A base item in the report view
    """
    def __init__(self):
        self.data = {}

    def update_pushlogurl(self, bisection):
        self.data['pushlog_url'] = bisection.handler.get_pushlog_url()

    def status_text(self):
        return "Looking for build data..."


class StartItem(ReportItem):
    """
    Report a started bisection
    """
    def update_pushlogurl(self, bisection):
        ReportItem.update_pushlogurl(self, bisection)
        handler = bisection.handler
        self.build_type = handler.build_type
        if handler.build_type == 'nightly':
            self.first, self.last = handler.get_date_range()
        else:
            self.first, self.last = handler.get_range()
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
            msg = "%%s inbound build: %s" % self.data['changeset']
        if self.verdict is not None:
            msg += ' (verdict: %s)' % self.verdict
        return msg % self.state_text


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
        slots = ('step_started', 'step_build_found', 'step_testing',
                 'step_finished', 'started', 'finished')
        if self.bisector:
            # disconnect previous bisector
            for name in slots:
                signal = getattr(self.bisector, name)
                slot = getattr(self, name)
                signal.disconnect(slot)
        if bisector:
            # connect the new bisector
            for name in slots:
                signal = getattr(bisector, name)
                slot = getattr(self, name)
                signal.connect(slot)
        self.bisector = bisector

    def rowCount(self, parent=QModelIndex()):
        return len(self.items)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            item = self.items[index.row()]
            return item.status_text()
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
            item.data.update(build_infos)
            self.append_item(item)
        else:
            # previous item is a step, just update it
            last_item.data.update(build_infos)
            last_item.state_text = 'Downloading'
            self.update_item(last_item)

    @Slot(object, int, object)
    def step_testing(self, bisection, build_infos):
        last_item = self.items[-1]
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

        html = ""
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
