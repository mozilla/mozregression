"""
Access to mozilla branches information.
"""

import re
from collections import defaultdict

from mozlog import get_proxy_logger

from mozregression.errors import MozRegressionError

LOG = get_proxy_logger('Branches')


class Branches(object):
    DEFAULT_REPO_URL = 'https://hg.mozilla.org/'

    def __init__(self):
        self._branches = {}
        self._aliases = {}
        self._categories = defaultdict(list)

    def set_branch(self, name, path, category='default'):
        assert name not in self._branches, "branch %s already defined" % name
        self._branches[name] = self.DEFAULT_REPO_URL + path
        self._categories[category].append(name)

    def get_branches(self, category=None):
        if category is None:
            return self._branches.keys()
        return self._categories[category]

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

    def get_category(self, branch_name_or_alias):
        name = self.get_name(branch_name_or_alias)
        for cat, names in self._categories.iteritems():
            if name in names:
                return cat


def create_branches():
    branches = Branches()

    branches.set_branch("mozilla-central", "mozilla-central")
    branches.set_branch("comm-central", "comm-central")

    # integration branches
    for name in ("autoland", "mozilla-inbound"):
        branches.set_branch(name, "integration/%s" % name,
                            category='integration')

    # release branches
    for name in ("comm-beta", "comm-release",
                 "mozilla-beta", "mozilla-release"):
        branches.set_branch(name, "releases/%s" % name, category='releases')

    branches.set_branch('try', 'try', category='try')

    # aliases
    for name, aliases in (
            ("mozilla-central", ("m-c", "central")),
            ("mozilla-inbound", ("m-i", "inbound", "mozilla inbound")),
            ("mozilla-beta", ("m-b", "beta")),
            ("mozilla-release", ("m-r", "release"))):
        for alias in aliases:
            branches.set_alias(alias, name)
    return branches


BRANCHES = create_branches()

# useful function aliases

get_url = BRANCHES.get_url
get_name = BRANCHES.get_name
get_branches = BRANCHES.get_branches
get_category = BRANCHES.get_category


RE_MERGE_BRANCH = re.compile(r"merge ([\w\s-]+) to ([\w\s-]+).*", re.I)


def find_branch_in_merge_commit(message, current_branch):
    """
    Try to extract the branch name where commits comes from in a merge commit
    message.

    Some commit messages incorrectly transpose the repo names.  If the first
    repo is the same as current_branch assume this is the case.

    Return None if the message does not looks like a merge commit.
    """
    match = RE_MERGE_BRANCH.match(message)
    if match:
        if get_name(match.group(1)) == current_branch:
            LOG.debug("Assuming transposed repos in merge commit message")
            return get_name(match.group(2))
        else:
            return get_name(match.group(1))
