
class MozRegressionError(Exception):
    """Base class for mozregression errors."""

class Win64NoAvailableBuildError(MozRegressionError):
    def __init__(self):
        MozRegressionError.__init__(self,
                                    "No builds available for 64 bit Windows"
                                    " (try specifying --bits=32)")

class WinTooOldBuildError(MozRegressionError):
    def __init__(self):
        MozRegressionError.__init__(self,
                                    "Can't run Windows builds before"
                                    " 2010-03-18")
