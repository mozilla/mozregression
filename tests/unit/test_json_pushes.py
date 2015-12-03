import pytest

from datetime import date
from mock import Mock
from mozregression.json_pushes import JsonPushes
from mozregression.errors import MozRegressionError, EmptyPushlogError


@pytest.mark.parametrize('branch,chsetskwargs,result_url', [
    ('mozilla-inbound', {'changeset': '1234'},
     "https://hg.mozilla.org/integration/mozilla-inbound/"
     "json-pushes?changeset=1234"),
    ('mozilla-inbound', {'fromchange': '12', 'tochange': '34'},
     "https://hg.mozilla.org/integration/mozilla-inbound/"
     "json-pushes?fromchange=12&tochange=34"),
])
def test_json_pushes_url(branch, chsetskwargs, result_url):
    jpushes = JsonPushes(branch=branch)
    assert jpushes.json_pushes_url(**chsetskwargs) == result_url


def test_pushlog_for_change(mocker):
    pushlog = {'a': 'b'}
    retry_get = mocker.patch('mozregression.json_pushes.retry_get')
    response = Mock(json=Mock(return_value={'1': pushlog}))
    retry_get.return_value = response

    jpushes = JsonPushes()
    assert jpushes.pushlog_for_change('validchangeset') == pushlog


def test_pushlog_for_change_404_error(mocker):
    retry_get = mocker.patch('mozregression.json_pushes.retry_get')
    response = Mock(status_code=404)
    retry_get.return_value = response

    jpushes = JsonPushes()
    with pytest.raises(MozRegressionError):
        jpushes.pushlog_for_change('invalid_changeset')


def test_pushlog_for_change_nothing_found(mocker):
    retry_get = mocker.patch('mozregression.json_pushes.retry_get')
    response = Mock(json=Mock(return_value={}))
    retry_get.return_value = response

    jpushes = JsonPushes()
    with pytest.raises(MozRegressionError):
        jpushes.pushlog_for_change('invalid_changeset')


def test_pushlog_within_changes(mocker):
    push_first = {'1': {'date': 1}}
    other_pushes = {
        '2': {'date': 2},
        '3': {'date': 3}
    }

    retry_get = mocker.patch('mozregression.json_pushes.retry_get')
    response = Mock(json=Mock(side_effect=[push_first, other_pushes]))
    retry_get.return_value = response

    jpushes = JsonPushes()
    assert jpushes.pushlog_within_changes('fromchset', "tochset") == [
        {'date': 1}, {'date': 2}, {'date': 3}
    ]

    # raw should include push ids in the result
    response = Mock(json=Mock(side_effect=[push_first, other_pushes]))
    retry_get.return_value = response

    assert jpushes.pushlog_within_changes(
        'fromchset', "tochset", raw=True
    ) == dict(push_first.items() + other_pushes.items())


def test_pushlog_within_changes_using_dates():
    p1 = {'changesets': ['abc'], 'date': 12345}
    p2 = {'changesets': ['def'], 'date': 67891}
    pushes = {'1': p1, '2': p2}

    jpushes = JsonPushes(branch='m-i')

    jpushes._request = Mock(return_value=pushes)

    assert jpushes.pushlog_within_changes(
        date(2015, 1, 1), date(2015, 2, 2)
    ) == [p1, p2]

    jpushes._request.assert_called_once_with(
        'https://hg.mozilla.org/integration/mozilla-inbound/json-pushes?'
        'startdate=2015-01-01&enddate=2015-02-03'
    )


def test_revision_for_date_raise_appropriate_error():
    jpushes = JsonPushes(branch='inbound')
    jpushes.pushlog_within_changes = Mock(side_effect=EmptyPushlogError)

    with pytest.raises(EmptyPushlogError) as ctx:
        jpushes.revision_for_date(date(2015, 1, 1))

    assert str(ctx.value) == \
        'No pushes available for the date 2015-01-01 on inbound.'
