"""
Date utilities functions.
"""

from __future__ import absolute_import

import calendar
import datetime
import re

from mozregression.errors import DateFormatError, DateValueError


def parse_date(date_string):
    """
    Returns a date or a datetime from a string.
    """
    if len(date_string) == 14 and date_string.isdigit():
        # probably a build id - transform that in a datetime
        try:
            return datetime.datetime.strptime(date_string, "%Y%m%d%H%M%S")
        except ValueError:
            raise DateFormatError(date_string, "Not a valid build id: `%s`")
    regex = re.compile(r"(\d{4})\-(\d{1,2})\-(\d{1,2})")
    matched = regex.match(date_string)
    if not matched:
        raise DateFormatError(date_string)
    try:
        return datetime.date(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))
    except ValueError as ex:
        raise DateValueError(date_string, ex)


def to_datetime(date):
    """
    transform a date to a datetime instance
    If the parameter is not a date, it is returned without modification
    """
    if isinstance(date, datetime.date):
        return datetime.datetime.combine(date, datetime.time())
    return date


def to_date(date_time):
    """
    transform a datetime to a date instance
    If the parameter is not a datetime, it is returned without modification
    """
    if isinstance(date_time, datetime.datetime):
        return date_time.date()
    return date_time


def is_date_or_datetime(obj):
    return isinstance(obj, (datetime.date, datetime.datetime))


def to_utc_timestamp(date_time):
    return calendar.timegm(date_time.timetuple())
