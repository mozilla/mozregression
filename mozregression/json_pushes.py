from mozregression.errors import MozRegressionError
from mozregression.network import retry_get


class JsonPushes(object):
    """
    Find pushlog json objects from a mozilla hg json-pushes api.
    """
    def __init__(self, path='integration', branch='mozilla-inbound'):
        self.path = path
        self.branch = branch

    def repo_url(self):
        return "https://hg.mozilla.org/%s/%s" % (self.path, self.branch)

    def json_pushes_url(self, changeset=None, fromchange=None, tochange=None):
        base_url = '%s/json-pushes?' % self.repo_url()
        if changeset:
            return base_url + ('changeset=%s' % changeset)
        else:
            return base_url + (
                'fromchange=%s&tochange=%s' % (fromchange, tochange))

    def _request(self, url, check_changeset):
        response = retry_get(url)
        if response.status_code == 404:
            raise MozRegressionError(
                "The url %r returned a 404 error. Please check the"
                " validity of the given changeset %r." %
                (url, check_changeset)
            )
        response.raise_for_status()
        pushlog = response.json()
        if not pushlog:
            raise MozRegressionError(
                "The url %r contains no pushlog. Please check the"
                " validity of the given changeset %r." %
                (url, check_changeset)
            )
        return pushlog

    def pushlog_for_change(self, changeset):
        """
        Returns the json pushlog object that match the given changeset.

        A MozRegressionError is thrown if None is found.
        """
        return next(self._request(
            self.json_pushes_url(changeset=changeset),
            changeset
        ).itervalues())

    def pushlog_within_changes(self, fromchange, tochange):
        """
        Returns pushlog json objects (python dicts) sorted by date.

        The result will contains all pushlogs including the pushlogs for
        fromchange and tochange.

        This will return at least one pushlog. If changesets are not valid
        it will raise a MozRegressionError.
        """
        # the first changeset is not taken into account in the result.
        # let's add it directly with this request
        chsets = self._request(
            self.json_pushes_url(changeset=fromchange),
            fromchange
        )

        # now fetch all remaining changesets
        chsets.update(self._request(
            self.json_pushes_url(fromchange=fromchange, tochange=tochange),
            # if we have an error, this is for sure because of the
            # tochange changeset, because we checked the fromchange previously.
            tochange
        ))
        # sort pushlogs by date
        return sorted(chsets.itervalues(), key=lambda push: push['date'])
