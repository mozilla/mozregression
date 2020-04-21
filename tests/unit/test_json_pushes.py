from __future__ import absolute_import

from datetime import date, datetime

import pytest
from mock import Mock, call

from mozregression.errors import EmptyPushlogError, MozRegressionError
from mozregression.json_pushes import JsonPushes, Push


def test_push(mocker):
    pushlog = {"1": {"changesets": ["a", "b", "c"], "date": 123456}}
    retry_get = mocker.patch("mozregression.json_pushes.retry_get")
    response = Mock(json=Mock(return_value=pushlog))
    retry_get.return_value = response

    jpushes = JsonPushes()
    push = jpushes.push("validchangeset")
    assert isinstance(push, Push)
    assert push.push_id == "1"
    assert push.changeset == "c"
    assert push.changesets[0] == "a"
    assert push.timestamp == 123456
    assert push.utc_date == datetime(1970, 1, 2, 10, 17, 36)
    assert str(push) == "c"
    retry_get.assert_called_once_with(
        "https://hg.mozilla.org/mozilla-central/json-pushes" "?changeset=validchangeset"
    )


def test_push_404_error(mocker):
    retry_get = mocker.patch("mozregression.json_pushes.retry_get")
    response = Mock(status_code=404, json=Mock(return_value={"error": "unknown revision"}))
    retry_get.return_value = response

    jpushes = JsonPushes()
    with pytest.raises(MozRegressionError):
        jpushes.push("invalid_changeset")


def test_push_nothing_found(mocker):
    retry_get = mocker.patch("mozregression.json_pushes.retry_get")
    response = Mock(json=Mock(return_value={}))
    retry_get.return_value = response

    jpushes = JsonPushes()
    with pytest.raises(MozRegressionError):
        jpushes.push("invalid_changeset")


def test_pushes_within_changes(mocker):
    push_first = {"1": {"changesets": ["a"]}}
    other_pushes = {"2": {"changesets": ["b"]}, "3": {"changesets": ["c"]}}

    retry_get = mocker.patch("mozregression.json_pushes.retry_get")
    response = Mock(json=Mock(side_effect=[push_first, other_pushes]))
    retry_get.return_value = response

    jpushes = JsonPushes()
    pushes = jpushes.pushes_within_changes("fromchset", "tochset")

    assert pushes[0].push_id == "1"
    assert pushes[0].changeset == "a"
    assert pushes[1].push_id == "2"
    assert pushes[1].changeset == "b"
    assert pushes[2].push_id == "3"
    assert pushes[2].changeset == "c"

    retry_get.assert_has_calls(
        [
            call("https://hg.mozilla.org/mozilla-central/json-pushes" "?changeset=fromchset"),
            call(
                "https://hg.mozilla.org/mozilla-central/json-pushes"
                "?fromchange=fromchset&tochange=tochset"
            ),
        ]
    )


def test_pushes_within_changes_using_dates(mocker):
    p1 = {"changesets": ["abc"], "date": 12345}
    p2 = {"changesets": ["def"], "date": 67891}
    pushes = {"1": p1, "2": p2}

    retry_get = mocker.patch("mozregression.json_pushes.retry_get")
    retry_get.return_value = Mock(json=Mock(return_value=pushes))

    jpushes = JsonPushes(branch="m-i")

    pushes = jpushes.pushes_within_changes(date(2015, 1, 1), date(2015, 2, 2))
    assert pushes[0].push_id == "1"
    assert pushes[1].push_id == "2"

    retry_get.assert_called_once_with(
        "https://hg.mozilla.org/integration/mozilla-inbound/json-pushes?"
        "enddate=2015-02-03&startdate=2015-01-01"
    )


def test_push_with_date_raise_appropriate_error():
    jpushes = JsonPushes(branch="inbound")
    jpushes.pushes_within_changes = Mock(side_effect=EmptyPushlogError)

    with pytest.raises(EmptyPushlogError) as ctx:
        jpushes.push(date(2015, 1, 1))

    assert str(ctx.value) == "No pushes available for the date 2015-01-01 on inbound."
