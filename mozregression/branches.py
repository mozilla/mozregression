"""
Access to mozilla branches information.
"""

from mozregression.errors import MozRegressionError


class Branches(object):
    DEFAULT_REPO_URL = 'https://hg.mozilla.org/'

    def __init__(self):
        self._branches = {}
        self._aliases = {}

    def set_branch(self, name, path):
        assert name not in self._branches, "branch %s already defined" % name
        self._branches[name] = self.DEFAULT_REPO_URL + path

    def get_branches(self):
        return self._branches.keys()

    def set_alias(self, alias, branch_name):
        assert alias not in self._aliases, "alias %s already defined" % alias
        assert branch_name in self._branches, "no such branch %s" % branch_name
        self._aliases[alias] = branch_name

    def get_url(self, branch_name_or_alias):
        try:
            return self._branches[self.get_name(branch_name_or_alias)]
        except KeyError:
            raise MozRegressionError(
                "No such branch '%s'." % branch_name_or_alias)

    def get_name(self, branch_name_or_alias):
        return self._aliases.get(branch_name_or_alias) or branch_name_or_alias


def create_branches():
    branches = Branches()

    branches.set_branch("mozilla-central", "mozilla-central")

    # integration branches
    for name in ("b2g-inbound", "fx-team", "mozilla-inbound"):
        branches.set_branch(name, "integration/%s" % name)

    # release branches
    for name in ("comm-aurora", "comm-beta", "comm-release", "mozilla-aurora",
                 "mozilla-beta", "mozilla-release"):
        branches.set_branch(name, "releases/%s" % name)

    # aliases
    for name, aliases in (
            ("mozilla-central", ("m-c", "central")),
            ("mozilla-inbound", ("m-i", "inbound")),
            ("mozilla-aurora", ("aurora",)),
            ("mozilla-beta", ("beta",)),
            ("fx-team", ("f-t",)),
            ("b2g-inbound", ("b2ginbound", "b2g-i", "b-i"))):
        for alias in aliases:
            branches.set_alias(alias, name)
    return branches


BRANCHES = create_branches()

# useful function aliases

get_url = BRANCHES.get_url
get_name = BRANCHES.get_name
