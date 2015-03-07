from PySide.QtCore import QAbstractTableModel, QModelIndex, Qt, \
    Slot

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

    @Slot(object)
    def attach_bisector(self, bisector):
        bisector.step_started.connect(self.step_started)
        bisector.step_build_found.connect(self.step_build_found)
        bisector.step_finished.connect(self.step_finished)
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

    @Slot(object, int)
    def step_started(self, bisection, step_num):
        self.beginInsertRows(QModelIndex(), step_num-1, step_num-1)
        self.step_reports.append(StepReport())
        self.endInsertRows()

    @Slot(object, int, object)
    def step_build_found(self, bisection, step_num, build_infos):
        step_report = self.step_reports[step_num-1]
        step_report.build_infos = build_infos
        self.update_step_report(step_report)

    @Slot(object, int, str)
    def step_finished(self, bisection, step_num, verdict):
        step_report = self.step_reports[step_num-1]
        step_report.verdict = verdict
        self.update_step_report(step_report)

    @Slot(object, int)
    def finished(self, bisection, result):
        # remove the last insterted step
        index = len(self.step_reports) -1
        self.beginRemoveRows(QModelIndex(), index, index)
        self.step_reports.pop(index)
        self.endRemoveRows()
