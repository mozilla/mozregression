import pytest

from mock import Mock
from mozregression.json_pushes import JsonPushes
from mozregression.errors import MozRegressionError


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
