#!/usr/bin/env python

import os
import re

UNWANTED_LIBRARIES = [
    "Qt3DAnimation",
    "Qt3DCore",
    "Qt3DExtras",
    "Qt3DInput",
    "Qt3DLogic",
    "Qt3DRender",
    "QtCharts",
    "QtConcurrent",
    "QtDataVisualization",
    "QtHelp",
    "QtLocation",
    "QtMultimedia",
    "QtMultimediaWidgets",
    "QtNetwork",
    "QtOpenGL",
    "QtPositioning",
    "QtPrintSupport",
    "QtQml",
    "QtQuick",
    "QtQuickWidgets",
    "QtScxml",
    "QtSensors",
    "QtSql",
    "QtSvg",
    "QtTextToSpeech",
    "QtWebChannel",
    "QtWebEngineCore",
    "QtWebEngineWidgets",
    "QtWebSockets",
    "QtXml",
    "QtXmlPatterns",
]

unwanted_re = "|".join(UNWANTED_LIBRARIES)
for root, dirs, filenames in os.walk("."):
    qt_filenames = [
        os.path.join(root, filename) for filename in filenames if re.match(unwanted_re, filename)
    ]
    for qt_filename in qt_filenames:
        os.unlink(qt_filename)
