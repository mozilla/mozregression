from __future__ import absolute_import

import datetime

from mozlog import get_proxy_logger

from mozregression import branches
from mozregression.dates import is_date_or_datetime
from mozregression.errors import EmptyPushlogError
from mozregression.network import retry_get

LOG = get_proxy_logger("JsonPushes")


class Push(object):
    """
    Simple wrapper around a json push object from json-pushes API.
    """

    __slots__ = ("_data", "_push_id")  # to save memory usage

    def __init__(self, push_id, data):
        self._data = data
        self._push_id = push_id

    @property
    def push_id(self):
        return self._push_id

    @property
    def changesets(self):
        return self._data["changesets"]

    @property
    def changeset(self):
        """
        Returns the last changeset in the push (the most interesting for us)
        """
        return self._data["changesets"][-1]

    @property
    def timestamp(self):
        return self._data["date"]

    @property
    def utc_date(self):
        return datetime.datetime.utcfromtimestamp(self.timestamp)

    def __str__(self):
        return self.changeset[:12]


class JsonPushes(object):
    """
    Find pushlog Push objects from a mozilla hg json-pushes api.
    """

    def __init__(self, branch="mozilla-central"):
        self.branch = branch
        self.repo_url = branches.get_url(branch)

    def pushes(self, **kwargs):
        """
        Returns a sorted lists of Push objects. The list can not be empty.

        Basically issue a raw request to the server.
        """
        base_url = "%s/json-pushes?" % self.repo_url
        url = base_url + "&".join(sorted("%s=%s" % kv for kv in kwargs.items()))
        LOG.debug("Using url: %s" % url)

        response = retry_get(url)
        data = response.json()

        if (
            response.status_code == 404
            and data is not None
            and "error" in data
            and "unknown revision" in data["error"]
        ):
            raise EmptyPushlogError(
                "The url %r returned a 404 error because the push is not"
                " in this repo (e.g., not merged yet)." % url
            )
        response.raise_for_status()

        if not data:
            raise EmptyPushlogError(
                "The url %r contains no pushlog. Maybe use another range ?" % url
            )

        pushlog = []
        for key in sorted(data):
            pushlog.append(Push(key, data[key]))
        return pushlog

    def pushes_within_changes(self, fromchange, tochange, verbose=True, **kwargs):
        """
        Returns a list of Push objects, including fromchange and tochange.

        This will return at least one Push. In case of error it will raise
        a MozRegressionError.
        """
        from_is_date = is_date_or_datetime(fromchange)
        to_is_date = is_date_or_datetime(tochange)

        kwargs = {}
        if not from_is_date:
            # the first changeset is not taken into account in the result.
            # let's add it directly with this request
            chsets = self.pushes(changeset=fromchange)
            kwargs["fromchange"] = fromchange
        else:
            chsets = []
            kwargs["startdate"] = fromchange.strftime("%Y-%m-%d")

        if not to_is_date:
            kwargs["tochange"] = tochange
        else:
            # add one day to take the last day in account
            kwargs["enddate"] = (tochange + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        # now fetch all remaining changesets
        chsets.extend(self.pushes(**kwargs))

        log = LOG.info if verbose else LOG.debug
        if from_is_date:
            first = chsets[0]
            log(
                "Using {} (pushed on {}) for date {}".format(
                    first.changeset, first.utc_date, fromchange
                )
            )
        if to_is_date:
            last = chsets[-1]
            log(
                "Using {} (pushed on {}) for date {}".format(
                    last.changeset, last.utc_date, tochange
                )
            )

        return chsets

    def push(self, changeset, **kwargs):
        """
        Returns the Push object that match the given changeset or date.

        A MozRegressionError is thrown if None is found.
        """
        if is_date_or_datetime(changeset):
            try:
                return self.pushes_within_changes(changeset, changeset, verbose=False)[-1]
            except EmptyPushlogError:
                raise EmptyPushlogError(
                    "No pushes available for the date %s on %s." % (changeset, self.branch)
                )
        return self.pushes(changeset=changeset, **kwargs)[0]
