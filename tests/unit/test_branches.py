from mozregression import branches, errors
import pytest


@pytest.mark.parametrize('branch,alias', [
    ("mozilla-inbound", "mozilla-inbound"),
    ("mozilla-inbound", "m-i"),
    ("mozilla-central", "mozilla-central"),
    ("mozilla-central", "m-c"),
    ("unknown", "unknown")
])
def test_branch_name(branch, alias):
    assert branch == branches.get_name(alias)


@pytest.mark.parametrize('branch,url', [
    ("m-c",
     "https://hg.mozilla.org/mozilla-central"),
    ("m-i",
     "https://hg.mozilla.org/integration/mozilla-inbound"),
    ("mozilla-aurora",
     "https://hg.mozilla.org/releases/mozilla-aurora")
])
def test_get_urls(branch, url):
    assert branches.get_url(branch) == url


def test_get_branches():
    names = branches.get_branches()
    assert 'mozilla-central' in names
    # no aliases returned
    assert 'm-c' not in names


def test_get_url_unknown_branch():
    with pytest.raises(errors.MozRegressionError):
        branches.get_url("unknown branch")


@pytest.mark.parametrize('commit, branch', [
    ("Merge mozilla-central to fx-team",
     "mozilla-central"),
    ("Merge fx-team to central, a=merge",
     "fx-team"),
    ("Merge m-c to b2g-inbound",
     "mozilla-central"),
    ("Merge b2ginbound to central, a=merge",
     "b2g-inbound"),
    ("Merge m-c to b2ginbound, a=merge CLOSED TREE",
     "mozilla-central"),
    ("merge f-t to mozilla-central a=merge",
     "fx-team"),
    ("Merge m-i to m-c, a=merge CLOSED TREE",
     "mozilla-inbound"),
])
def test_find_branch_in_merge_commit(commit, branch):
    assert branches.find_branch_in_merge_commit(commit) == branch
