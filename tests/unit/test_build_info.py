from __future__ import absolute_import

from datetime import date, datetime

import pytest

from mozregression import build_info
from mozregression.fetch_configs import create_config


def create_build_info(klass, **attrs):
    defaults = dict(
        fetch_config=create_config("firefox", "linux", 64, "x86_64"),
        build_url="http://build/url",
        build_date=date(2015, 9, 1),
        changeset="12ab" * 10,
        repo_url="http://repo:url",
    )
    defaults.update(attrs)
    return klass(**defaults)


def read_only(klass):
    defaults = [
        ("app_name", "firefox"),
        ("build_url", "http://build/url"),
        ("build_date", date(2015, 9, 1)),
        ("changeset", "12ab" * 10),
        ("short_changeset", "12ab12ab"),
        ("repo_url", "http://repo:url"),
    ]
    if klass is build_info.NightlyBuildInfo:
        defaults.extend([("repo_name", "mozilla-central"), ("build_type", "nightly")])
    else:
        defaults.extend([("repo_name", "mozilla-central"), ("build_type", "integration")])
    return [(klass, attr, value) for attr, value in defaults]


@pytest.mark.parametrize(
    "klass, attr, value",
    read_only(build_info.NightlyBuildInfo) + read_only(build_info.IntegrationBuildInfo),
)
def test_read_only_attrs(klass, attr, value):
    binfo = create_build_info(klass)
    assert getattr(binfo, attr) == value
    with pytest.raises(AttributeError):
        # can't set attribute
        setattr(binfo, attr, value)


@pytest.mark.parametrize(
    "klass, attr, value",
    [
        (build_info.NightlyBuildInfo, "build_file", "/build/file"),
        (build_info.IntegrationBuildInfo, "build_file", "/build/file"),
    ],
)
def test_writable_attrs(klass, attr, value):
    binfo = create_build_info(klass)
    setattr(binfo, attr, value)
    assert getattr(binfo, attr) == value


@pytest.mark.parametrize("klass", [build_info.NightlyBuildInfo, build_info.IntegrationBuildInfo])
def test_update_from_app_info(klass):
    app_info = {
        "application_changeset": "chset",
        "application_repository": "repo",
    }
    binfo = create_build_info(klass, changeset=None, repo_url=None)
    assert binfo.changeset is None
    assert binfo.repo_url is None
    binfo.update_from_app_info(app_info)
    # binfo updated
    assert binfo.changeset == "chset"
    assert binfo.repo_url == "repo"

    binfo = create_build_info(klass)
    # if values were defined, nothing is updated
    assert binfo.changeset is not None
    assert binfo.repo_url is not None
    binfo.update_from_app_info(app_info)
    assert binfo.changeset != "chset"
    assert binfo.repo_url != "repo"


@pytest.mark.parametrize("klass", [build_info.NightlyBuildInfo, build_info.IntegrationBuildInfo])
def test_to_dict(klass):
    binfo = create_build_info(klass)
    dct = binfo.to_dict()
    assert isinstance(dct, dict)
    assert "app_name" in dct
    assert dct["app_name"] == "firefox"


@pytest.mark.parametrize(
    "klass,extra,result",
    [
        # build with defaults given in create_build_info
        (build_info.NightlyBuildInfo, {}, "2015-09-01--mozilla-central--url"),
        # this time with a datetime instance (buildid)
        (
            build_info.NightlyBuildInfo,
            {"build_date": datetime(2015, 11, 16, 10, 2, 5)},
            "2015-11-16-10-02-05--mozilla-central--url",
        ),
        # same but for integration
        (
            build_info.IntegrationBuildInfo,
            {},
            "12ab12ab12ab-shippable--mozilla-central--url",
        ),
    ],
)
def test_persist_filename(klass, extra, result):
    persist_part = extra.pop("persist_part", None)
    binfo = create_build_info(klass, **extra)
    if persist_part:
        # fake that the fetch config should return the persist_part
        binfo._fetch_config.integration_persist_part = lambda: persist_part
    assert binfo.persist_filename == result


@pytest.mark.parametrize(
    "arch,result",
    [
        ("arm", "2015-09-01--mozilla-central--arm--url"),
        ("x86_64", "2015-09-01--mozilla-central--x86_64--url"),
        (None, "2015-09-01--mozilla-central--arm--url"),
    ],
)
def test_persist_filename_with_arch(arch, result):
    binfo_args = {
        "fetch_config": create_config("gve", "linux", None, "x86", arch),
    }
    binfo = create_build_info(build_info.NightlyBuildInfo, **binfo_args)
    assert binfo.persist_filename == result
