import datetime

from mozlog import get_default_logger

from mozregression.errors import MozRegressionError, EmptyPushlogError
from mozregression.network import retry_get
from mozregression import branches
from mozregression.dates import is_date_or_datetime


class JsonPushes(object):
    """
    Find pushlog json objects from a mozilla hg json-pushes api.
    """
    def __init__(self, branch='mozilla-inbound'):
        self.branch = branch
        self._repo_url = branches.get_url(branch)
        self.logger = get_default_logger("JsonPushes")

    def repo_url(self):
        return self._repo_url

    def json_pushes_url(self, **kwargs):
        base_url = '%s/json-pushes?' % self.repo_url()
        url = base_url + '&'.join("%s=%s" % kv for kv in kwargs.iteritems())
        self.logger.debug("Using url: %s" % url)
        return url

    def _request(self, url):
        response = retry_get(url)
        if response.status_code == 404:
            raise MozRegressionError(
                "The url %r returned a 404 error. Please check the"
                " validity of the url." % url
            )
        response.raise_for_status()
        pushlog = response.json()
        if not pushlog:
            raise EmptyPushlogError(
                "The url %r contains no pushlog. Maybe use another range ?"
                % url
            )
        return pushlog

    def pushlog_for_change(self, changeset, **kwargs):
        """
        Returns the json pushlog object that match the given changeset.

        A MozRegressionError is thrown if None is found.
        """
        return next(self._request(
            self.json_pushes_url(changeset=changeset, **kwargs)
        ).itervalues())

    def pushlog_within_changes(self, fromchange, tochange, raw=False,
                               verbose=True):
        """
        Returns pushlog json objects (python dicts).

        The result will contains all pushlogs including the pushlogs for
        fromchange and tochange. These parameters can be dates (date or
        datetime instances) or changesets (str objects).

        This will return at least one pushlog. In case of error it will raise
        a MozRegressionError.
        """
        from_is_date = is_date_or_datetime(fromchange)
        to_is_date = is_date_or_datetime(tochange)

        kwargs = {}
        if not from_is_date:
            # the first changeset is not taken into account in the result.
            # let's add it directly with this request
            chsets = self._request(self.json_pushes_url(changeset=fromchange))
            kwargs['fromchange'] = fromchange
        else:
            chsets = {}
            kwargs['startdate'] = fromchange.strftime('%Y-%m-%d')

        if not to_is_date:
            kwargs['tochange'] = tochange
        else:
            # add one day to take the last day in account
            kwargs['enddate'] = tochange + datetime.timedelta(days=1)

        # now fetch all remaining changesets
        chsets.update(self._request(self.json_pushes_url(**kwargs)))

        ordered = sorted(chsets)

        log = self.logger.info if verbose else self.logger.debug
        if from_is_date:
            first = chsets[ordered[0]]
            log("Using {} (pushed on {}) for date {}".format(
                first['changesets'][-1],
                datetime.datetime.utcfromtimestamp(first['date']),
                fromchange,
            ))
        if to_is_date:
            last = chsets[ordered[-1]]
            log("Using {} (pushed on {}) for date {}".format(
                last['changesets'][-1],
                datetime.datetime.utcfromtimestamp(last['date']),
                tochange,
            ))

        if raw:
            return chsets
        # sort pushlogs by push id
        return [chsets[k] for k in ordered]

    def revision_for_date(self, date):
        """
        Returns the last revision that matches the given date.

        Raise an explicit EmptyPushlogError if no pushes are available.
        """
        try:
            return self.pushlog_within_changes(
                date, date, verbose=False
            )[-1]['changesets'][-1]
        except EmptyPushlogError:
            raise EmptyPushlogError(
                "No pushes available for the date %s on %s."
                % (date, self.branch)
            )
