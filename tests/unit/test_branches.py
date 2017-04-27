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


@pytest.mark.parametrize('category,present,not_present', [
    # no category, list all branches but not aliases
    (None, ['mozilla-central', 'mozilla-inbound'], ['m-c', 'm-i']),
    # specific category list only branches under that category
    ('integration', ['mozilla-inbound'], ['m-i', 'mozilla-central']),
])
def test_get_branches(category, present, not_present):
    names = branches.get_branches(category=category)
    for name in present:
        assert name in names
    for name in not_present:
        assert name not in names


def test_get_url_unknown_branch():
    with pytest.raises(errors.MozRegressionError):
        branches.get_url("unknown branch")


@pytest.mark.parametrize('name, expected', [
    ('mozilla-central', 'default'),
    ('autoland', 'integration'),
    ('m-i', 'integration'),
    ('', None),
    (None, None)
])
def test_get_category(name, expected):
    assert branches.get_category(name) == expected


@pytest.mark.parametrize('commit, branch', [
    ("Merge mozilla-central to autoland",
     "mozilla-central"),
    ("Merge autoland to central, a=merge",
     "autoland"),
    ("merge autoland to mozilla-central a=merge",
     "autoland"),
    ("Merge m-i to m-c, a=merge CLOSED TREE",
     "mozilla-inbound"),
])
def test_find_branch_in_merge_commit(commit, branch):
    assert branches.find_branch_in_merge_commit(commit) == branch
