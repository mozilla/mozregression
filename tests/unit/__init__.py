from __future__ import absolute_import

from mozlog.structured import set_default_logger
from mozlog.structured.structuredlog import StructuredLogger

set_default_logger(StructuredLogger("mozregression.tests.unit"))
