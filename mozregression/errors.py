# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Definition of mozregression related exceptions.
"""


class MozRegressionError(Exception):
    """Base class for mozregression errors."""


class Win64NoAvailableBuildError(MozRegressionError):
    """
    Raised when a build is not available for windows 64 because it is too old.
    """
    def __init__(self):
        MozRegressionError.__init__(self,
                                    "No builds available for 64 bit Windows"
                                    " (try specifying --bits=32)")


class WinTooOldBuildError(MozRegressionError):
    """
    Raised when a windows build is too old.
    """
    def __init__(self):
        MozRegressionError.__init__(self,
                                    "Can't run Windows builds before"
                                    " 2010-03-18")


class DateFormatError(MozRegressionError):
    """
    Raised when a date can not be parsed from a string.
    """
    def __init__(self, date_string):
        MozRegressionError.__init__(self,
                                    "Incorrect date format: `%s`"
                                    % date_string)


class DownloadError(MozRegressionError):
    """
    Raised when a build can not be downloaded.
    """


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
        MozRegressionError.__init__(self,
                                    "Unable to find a matching date for"
                                    " release %s" % release)
