from PySide.QtGui import QPlainTextEdit, QTableView
from PySide.QtCore import QAbstractTableModel, QModelIndex, Qt, Slot, Signal


class StepReport(object):
    def __init__(self):
        self.build_infos = None
        self.verdict = None

    def status_text(self):
        if self.build_infos is None:
            return "Looking for build data..."
        if self.build_infos['build_type'] == 'nightly':
            msg = "Found nightly build: %s" % self.build_infos['build_date']
        else:
            msg = "Found inbound build: %s" % self.build_infos['changeset']
        if self.verdict is not None:
            msg += ' (verdict: %s)' % self.verdict
        return msg


class ReportModel(QAbstractTableModel):
    def __init__(self):
        QAbstractTableModel.__init__(self)
        self.step_reports = []
        self.__started_called = False

    def clear(self):
        self.beginResetModel()
        self.step_reports = []
        self.endResetModel()

    @Slot(object)
    def attach_bisector(self, bisector):
        bisector.step_started.connect(self.step_started)
        bisector.step_build_found.connect(self.step_build_found)
        bisector.step_finished.connect(self.step_finished)
        bisector.started.connect(self.started)
        bisector.finished.connect(self.finished)

    def rowCount(self, parent=QModelIndex()):
        return len(self.step_reports)

    def columnCount(self, parent=QModelIndex()):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            step_report = self.step_reports[index.row()]
            return step_report.status_text()
        return None

    def update_step_report(self, step_report):
        index = self.createIndex(self.step_reports.index(step_report), 0)
        self.dataChanged.emit(index, index)

    @Slot()
    def started(self):
        step_num = self.rowCount()
        self.beginInsertRows(QModelIndex(), step_num, step_num)
        self.step_reports.append(StepReport())
        self.endInsertRows()
        self.__started_called = True

    @Slot(object, int)
    def step_started(self, bisection):
        step_num = self.rowCount()
        if self.__started_called:
            self.__started_called = False
            return  # do nothing as we already created the row with started()
        self.beginInsertRows(QModelIndex(), step_num, step_num)
        self.step_reports.append(StepReport())
        self.endInsertRows()

    @Slot(object, int, object)
    def step_build_found(self, bisection, build_infos):
        step_report = self.step_reports[-1]
        step_report.build_infos = build_infos
        self.update_step_report(step_report)

    @Slot(object, int, str)
    def step_finished(self, bisection, verdict):
        step_report = self.step_reports[-1]
        step_report.verdict = verdict
        self.update_step_report(step_report)

    @Slot(object, int)
    def finished(self, bisection, result):
        # remove the last insterted step
        index = len(self.step_reports) - 1
        self.beginRemoveRows(QModelIndex(), index, index)
        self.step_reports.pop(index)
        self.endRemoveRows()


class ReportView(QTableView):
    step_report_selected = Signal(object)

    def __init__(self, parent=None):
        QTableView.__init__(self, parent)
        self._model = ReportModel()
        self.setModel(self._model)

    def currentChanged(self, current, previous):
        step_report = self._model.step_reports[current.row()]
        self.step_report_selected.emit(step_report)


class BuildInfoTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        QPlainTextEdit.__init__(self, parent)

    @Slot(object)
    def update_content(self, step_report):
        self.clear()
        if step_report.build_infos is not None:
            text = ""
            for k, v in step_report.build_infos.iteritems():
                text += "%s: %s\n" % (k, v)
            self.setPlainText(text)
