"""
Definition of mozregression related exceptions.
"""


class MozRegressionError(Exception):
    """Base class for mozregression errors."""


class WinTooOldBuildError(MozRegressionError):
    """
    Raised when a windows build is too old.
    """

    def __init__(self):
        MozRegressionError.__init__(self, "Can't run Windows builds before" " 2010-03-18")


class UnsupportedVersionError(MozRegressionError):
    """
    Raised when a build's Firefox version is too old to be driven by the
    Firefox DevTools MCP used by the ``--prompt`` option.
    """

    def __init__(self, build, min_version):
        MozRegressionError.__init__(
            self,
            "Build %s is too old for --prompt: the Firefox DevTools MCP requires"
            " Firefox %s or later. Narrow the regression range, or lower"
            " --prompt-min-version if you know it works on older builds." % (build, min_version),
        )


class DateFormatError(MozRegressionError):
    """
    Raised when a date can not be parsed from a string.
    """

    def __init__(self, date_string, format="Incorrect date format: `%s`"):
        MozRegressionError.__init__(self, format % date_string)


class DateValueError(MozRegressionError):
    """
    Raised when the integer values of a parsed date are invalid.
    """

    def __init__(self, date_string, ex, format="Invalid date value: `%s`, %s"):
        MozRegressionError.__init__(self, format % (date_string, ex))


class LauncherNotRunnable(MozRegressionError):
    """
    Raised when a :class:`mozregression.launchers.Launcher` can not be
    run on the system.
    """


class TestCommandError(MozRegressionError):
    """
    Raised on a user test command error.
    """


class UnavailableRelease(MozRegressionError):
    """
    Raised when firefox release is not available.
    """

    def __init__(self, release):
        MozRegressionError.__init__(
            self, "Unable to find a matching date for" " release %s" % release
        )


class LauncherError(MozRegressionError):
    """
    Error when running the tested application.
    """


class BuildInfoNotFound(MozRegressionError):
    """
    Raised when we can't find information about a build.
    """


class EmptyPushlogError(MozRegressionError):
    """
    Raised when there is no pushes in a given range
    """


class GoodBadExpectationError(MozRegressionError):
    """
    Raised when a build status is not what we expected at the beginning of a
    bisection.
    """
