__version__ = '0.9.46'

# import widget classes to make them accessible to generated
# ui files (maybe there is a better way of doing this?)
from .log_report import LogView
from .report import (BuildInfoTextBrowser, ReportView)

LogView = LogView
