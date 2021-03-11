from __future__ import absolute_import

import datetime
import re
import unittest

import pytest

from mozregression.dates import to_utc_timestamp
from mozregression.fetch_configs import (
    ARCHIVE_BASE_URL,
    TIMESTAMP_FENNEC_API_15,
    TIMESTAMP_FENNEC_API_16,
    FirefoxConfig,
    FirefoxL10nConfig,
    create_config,
    errors,
    get_build_regex,
)
from mozregression.json_pushes import Push

TIMESTAMP_TEST = to_utc_timestamp(datetime.datetime(2017, 11, 14, 0, 0, 0))


def create_push(chset, timestamp):
    return Push(1, {"changesets": [chset], "date": timestamp})


class TestFirefoxConfigLinux64(unittest.TestCase):
    app_name = "firefox"
    os = "linux"
    bits = 64
    processor = "x86_64"

    build_examples = ["firefox-38.0a1.en-US.linux-x86_64.tar.bz2"]
    build_info_examples = ["firefox-38.0a1.en-US.linux-x86_64.txt"]

    instance_type = FirefoxConfig

    def setUp(self):
        self.conf = create_config(self.app_name, self.os, self.bits, self.processor)

    def test_instance(self):
        self.assertIsInstance(self.conf, self.instance_type)

    def test_build_regex(self):
        for example in self.build_examples:
            res = re.match(self.conf.build_regex(), example)
            self.assertIsNotNone(res)

    def test_build_info_regex(self):
        for example in self.build_info_examples:
            res = re.match(self.conf.build_info_regex(), example)
            self.assertIsNotNone(res)

    def test_get_nightly_base_url(self):
        base_url = self.conf.get_nightly_base_url(datetime.date(2008, 6, 27))
        self.assertEqual(base_url, ARCHIVE_BASE_URL + "/firefox/nightly/2008/06/")

    def test_get_nightly_base_url_with_specific_base(self):
        self.conf.set_base_url("http://ftp-origin-scl3.mozilla.org/pub/")
        self.assertEqual(
            "http://ftp-origin-scl3.mozilla.org/pub/firefox/nightly/2008/06/",
            self.conf.get_nightly_base_url(datetime.date(2008, 6, 27)),
        )

    def test_nightly_repo_regex(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008, 6, 15))
        self.assertEqual(repo_regex, "/2008-06-15-[\\d-]+trunk/$")
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008, 6, 27))
        self.assertEqual(repo_regex, "/2008-06-27-[\\d-]+mozilla-central/$")
        # test with a datetime instance (buildid)
        repo_regex = self.conf.get_nightly_repo_regex(datetime.datetime(2015, 11, 27, 6, 5, 58))
        self.assertEqual(repo_regex, "/2015-11-27-06-05-58-mozilla-central/$")

    def test_set_repo(self):
        self.conf.set_repo("foo-bar")
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008, 6, 27))
        self.assertEqual(repo_regex, "/2008-06-27-[\\d-]+foo-bar/$")
        # with a value of None, default is applied
        self.conf.set_repo(None)
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008, 6, 27))
        self.assertEqual(repo_regex, "/2008-06-27-[\\d-]+mozilla-central/$")


class TestFirefoxConfigLinux32(TestFirefoxConfigLinux64):
    bits = 32
    processor = "x86"
    build_examples = ["firefox-38.0a1.en-US.linux-i686.tar.bz2"]
    build_info_examples = ["firefox-38.0a1.en-US.linux-i686.txt"]


class TestFirefoxConfigWin64(TestFirefoxConfigLinux64):
    os = "win"
    build_examples = [
        "firefox-38.0a1.en-US.win64-x86_64.zip",
        "firefox-38.0a1.en-US.win64.zip",
    ]
    build_info_examples = [
        "firefox-38.0a1.en-US.win64-x86_64.txt",
        "firefox-38.0a1.en-US.win64.txt",
    ]


class TestFirefoxConfigWin32(TestFirefoxConfigWin64):
    bits = 32
    processor = "x86"
    build_examples = ["firefox-38.0a1.en-US.win32.zip"]
    build_info_examples = ["firefox-38.0a1.en-US.win32.txt"]


class TestFirefoxConfigMac(TestFirefoxConfigLinux64):
    os = "mac"
    build_examples = ["firefox-38.0a1.en-US.mac.dmg"]
    build_info_examples = ["firefox-38.0a1.en-US.mac.txt"]


class TestFirefoxl10nConfig(unittest.TestCase):
    app_name = "firefox-l10n"
    os = "linux"
    bits = 64
    processor = "x86_64"
    lang = "ar"

    instance_type = FirefoxL10nConfig

    build_examples = ["firefox-38.0a1.ar.linux-x86_64.tar.bz2"]
    build_info_examples = ["firefox-38.0a1.en-US.linux-x86_64.txt"]

    def setUp(self):
        self.conf = create_config(self.app_name, self.os, self.bits, self.processor)
        self.conf.set_lang(self.lang)

    def test_instance(self):
        self.assertIsInstance(self.conf, self.instance_type)

    def test_build_regex(self):
        for example in self.build_examples:
            res = re.match(self.conf.build_regex(), example)
            self.assertIsNotNone(res)

    def test_build_info_regex(self):
        for example in self.build_info_examples:
            res = re.match(self.conf.build_info_regex(), example)
            self.assertIsNotNone(res)

    def test_nightly_repo_regex(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2016, 1, 1))
        self.assertEqual(repo_regex, "/2016-01-01-[\\d-]+mozilla-central-l10n/$")

    def test_nightly_repo_regex_before_2005_10_19(self):
        with self.assertRaises(errors.MozRegressionError):
            self.conf.get_nightly_repo_regex(datetime.date(2005, 9, 7))


class TestThunderbirdConfig(unittest.TestCase):
    os = "linux"
    bits = 64
    processor = "x86_64"

    def setUp(self):
        self.conf = create_config("thunderbird", self.os, self.bits, self.processor)

    def test_nightly_repo_regex_before_2008_07_26(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008, 7, 25))
        self.assertEqual(repo_regex, "/2008-07-25-[\\d-]+trunk/$")

    def test_nightly_repo_regex_before_2009_01_09(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2009, 1, 8))
        self.assertEqual(repo_regex, "/2009-01-08-[\\d-]+comm-central/$")

    def test_nightly_repo_regex_before_2010_08_21(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2010, 8, 20))
        self.assertEqual(repo_regex, "/2010-08-20-[\\d-]+comm-central-trunk/$")

    def test_nightly_repo_regex_since_2010_08_21(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2010, 8, 21))
        self.assertEqual(repo_regex, "/2010-08-21-[\\d-]+comm-central/$")


class TestThunderbirdConfigWin(TestThunderbirdConfig):
    os = "win"

    def test_nightly_repo_regex_before_2008_07_26(self):
        with self.assertRaises(errors.WinTooOldBuildError):
            TestThunderbirdConfig.test_nightly_repo_regex_before_2008_07_26(self)

    def test_nightly_repo_regex_before_2009_01_09(self):
        with self.assertRaises(errors.WinTooOldBuildError):
            TestThunderbirdConfig.test_nightly_repo_regex_before_2009_01_09(self)


class TestFennecConfig(unittest.TestCase):
    def setUp(self):
        self.conf = create_config("fennec", "linux", 64, None)

    def test_get_nightly_repo_regex(self):
        regex = self.conf.get_nightly_repo_regex(datetime.date(2014, 12, 5))
        self.assertIn("mozilla-central-android", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2014, 12, 10))
        self.assertIn("mozilla-central-android-api-10", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2015, 1, 1))
        self.assertIn("mozilla-central-android-api-11", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2016, 1, 28))
        self.assertIn("mozilla-central-android-api-11", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2016, 1, 29))
        self.assertIn("mozilla-central-android-api-15", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2017, 8, 30))
        self.assertIn("mozilla-central-android-api-16", regex)

    def test_build_regex(self):
        regex = re.compile(self.conf.build_regex())
        self.assertTrue(regex.match("fennec-36.0a1.multi.android-arm.apk"))

    def test_build_info_regex(self):
        regex = re.compile(self.conf.build_info_regex())
        self.assertTrue(regex.match("fennec-36.0a1.multi.android-arm.txt"))


class TestGVEConfig(unittest.TestCase):
    def setUp(self):
        self.conf = create_config("gve", "linux", 64, None)

    def test_fallbacking(self):
        assert self.conf.build_type == "opt"
        self.conf._inc_used_build()
        assert self.conf.build_type == "shippable"
        # Check we wrap
        self.conf._inc_used_build()
        assert self.conf.build_type == "opt"


class TestGetBuildUrl(unittest.TestCase):
    def test_for_linux(self):
        self.assertEqual(
            get_build_regex("test", "linux", 32, "x86"),
            r"(target|test.*linux-i686)\.tar.bz2",
        )

        self.assertEqual(
            get_build_regex("test", "linux", 64, "x86_64"),
            r"(target|test.*linux-x86_64)\.tar.bz2",
        )

        self.assertEqual(
            get_build_regex("test", "linux", 64, "x86_64", with_ext=False),
            r"(target|test.*linux-x86_64)",
        )

    def test_for_win(self):
        self.assertEqual(get_build_regex("test", "win", 32, "x86"), r"(target|test.*win32)\.zip")
        self.assertEqual(
            get_build_regex("test", "win", 64, "x86_64"),
            r"(target|test.*win64(-x86_64)?)\.zip",
        )
        self.assertEqual(
            get_build_regex("test", "win", 64, "x86_64", with_ext=False),
            r"(target|test.*win64(-x86_64)?)",
        )
        self.assertEqual(
            get_build_regex("test", "win", 32, "aarch64"), r"(target|test.*win32)\.zip"
        )
        self.assertEqual(
            get_build_regex("test", "win", 64, "aarch64"),
            r"(target|test.*win64-aarch64)\.zip",
        )

    def test_for_mac(self):
        self.assertEqual(get_build_regex("test", "mac", 32, "x86"), r"(target|test.*mac.*)\.dmg")
        self.assertEqual(get_build_regex("test", "mac", 64, "x86_64"), r"(target|test.*mac.*)\.dmg")
        self.assertEqual(
            get_build_regex("test", "mac", 64, "x86_64", with_ext=False),
            r"(target|test.*mac.*)",
        )

    def test_unknown_os(self):
        with self.assertRaises(errors.MozRegressionError):
            get_build_regex("test", "unknown", 32, "x86")


class TestFallbacksConfig(TestFirefoxConfigLinux64):
    def setUp(self):
        self.conf = create_config(self.app_name, self.os, self.bits, self.processor)
        self.conf.BUILD_TYPE_FALLBACKS = {"opt": ("test", "fallback")}
        self.conf.set_build_type("opt")

    def test_fallbacking(self):
        assert self.conf.build_type == "opt"
        self.conf._inc_used_build()
        assert self.conf.build_type == "test"
        self.conf._inc_used_build()
        assert self.conf.build_type == "fallback"
        # Check we wrap
        self.conf._inc_used_build()
        assert self.conf.build_type == "opt"

    def test_fallback_routes(self):
        routes = list(self.conf.tk_routes(create_push("1a", TIMESTAMP_TEST)))
        assert len(routes) == 3
        assert routes[0] == ("gecko.v2.mozilla-central.revision.1a.firefox.linux64-opt")
        assert routes[2] == ("gecko.v2.mozilla-central.revision.1a.firefox.linux64-fallback")


class TestAarch64AvailableBuildTypes(unittest.TestCase):
    app_name = "firefox"
    os = "win"
    bits = 64
    processor = "aarch64"

    def setUp(self):
        self.conf = create_config(self.app_name, self.os, self.bits, self.processor)
        self.conf.BUILD_TYPES = (
            "excluded[win64]",
            "included[win64-aarch64]",
            "default",
        )

    def test_aarch64_build_types(self):
        build_types = self.conf.available_build_types()
        assert len(build_types) == 2
        assert "default" in build_types
        assert "included" in build_types
        assert "excluded" not in build_types


CHSET = "47856a21491834da3ab9b308145caa8ec1b98ee1"
CHSET12 = "47856a214918"


@pytest.mark.parametrize(
    "app,os,bits,processor,repo,push_date,expected",
    [
        # firefox
        (
            "firefox",
            "win",
            64,
            "aarch64",
            "m-i",
            TIMESTAMP_TEST,
            "gecko.v2.mozilla-inbound.shippable.revision.%s.firefox.win64-aarch64-opt" % CHSET,
        ),
        (
            "firefox",
            "win",
            32,
            "aarch64",
            "m-i",
            TIMESTAMP_TEST,
            "gecko.v2.mozilla-inbound.shippable.revision.%s.firefox.win32-opt" % CHSET,
        ),
        (
            "firefox",
            "mac",
            64,
            "x86_64",
            "m-i",
            TIMESTAMP_TEST,
            "gecko.v2.mozilla-inbound.shippable.revision.%s.firefox.macosx64-opt" % CHSET,
        ),
        (
            "firefox",
            "linux",
            64,
            "x86_64",
            "m-i",
            TIMESTAMP_TEST,
            "gecko.v2.mozilla-inbound.shippable.revision.%s.firefox.linux64-opt" % CHSET,
        ),
        (
            "firefox",
            "linux",
            64,
            "x86_64",
            "try",
            TIMESTAMP_TEST,
            "gecko.v2.try.shippable.revision.%s.firefox.linux64-opt" % CHSET,
        ),
        # fennec
        (
            "fennec",
            None,
            None,
            None,
            None,
            TIMESTAMP_FENNEC_API_15 - 1,
            "gecko.v2.mozilla-central.revision.%s.mobile.android-api-11-opt" % CHSET,
        ),
        (
            "fennec",
            None,
            None,
            None,
            None,
            TIMESTAMP_FENNEC_API_15,
            "gecko.v2.mozilla-central.revision.%s.mobile.android-api-15-opt" % CHSET,
        ),
        (
            "fennec",
            None,
            None,
            None,
            None,
            TIMESTAMP_FENNEC_API_16,
            "gecko.v2.mozilla-central.revision.%s.mobile.android-api-16-opt" % CHSET,
        ),
        # thunderbird
        (
            "thunderbird",
            "win",
            32,
            "x86_64",
            "comm-central",
            TIMESTAMP_TEST,
            "comm.v2.comm-central.revision.%s.thunderbird.win32-opt" % CHSET,
        ),
        (
            "thunderbird",
            "linux",
            64,
            "x86_64",
            "comm-beta",
            TIMESTAMP_TEST,
            "comm.v2.comm-beta.revision.%s.thunderbird.linux64-opt" % CHSET,
        ),
    ],
)
def test_tk_route(app, os, bits, processor, repo, push_date, expected):
    conf = create_config(app, os, bits, processor)
    conf.set_repo(repo)
    result = conf.tk_route(create_push(CHSET, push_date))
    assert result == expected


@pytest.mark.parametrize(
    "app,os,bits,processor,build_type,expected",
    [
        # firefox
        (
            "firefox",
            "linux",
            64,
            "x86_64",
            "asan",
            "gecko.v2.mozilla-central.revision.%s.firefox.linux64-asan" % CHSET,
        ),
        (
            "firefox",
            "linux",
            64,
            "x86_64",
            "shippable",
            "gecko.v2.mozilla-central.shippable.revision.%s.firefox.linux64-opt" % CHSET,
        ),
        # gve
        (
            "gve",
            "linux",
            64,
            "x86_64",
            "opt",
            "gecko.v2.mozilla-central.revision.%s.mobile.android-api-16-opt" % CHSET,
        ),
        (
            "gve",
            "linux",
            64,
            "x86_64",
            "shippable",
            "gecko.v2.mozilla-central.shippable.revision.%s.mobile.android-api-16-opt" % CHSET,
        ),
    ],
)
def test_tk_route_with_build_type(app, os, bits, processor, build_type, expected):
    conf = create_config(app, os, bits, processor)
    conf.set_build_type(build_type)
    result = conf.tk_route(create_push(CHSET, TIMESTAMP_TEST))
    assert result == expected


def test_set_build_type():
    conf = create_config("firefox", "linux", 64, "x86_64")
    assert conf.build_type == "shippable"  # desktop Fx default is shippable
    conf.set_build_type("debug")
    assert conf.build_type == "debug"


def test_set_bad_build_type():
    conf = create_config("firefox", "linux", 64, "x86_64")
    with pytest.raises(errors.MozRegressionError):
        conf.set_build_type("wrong build type")


def test_jsshell_build_info_regex():
    conf = create_config("jsshell", "linux", 64, "x86_64")
    assert re.match(conf.build_info_regex(), "firefox-38.0a1.en-US.linux-x86_64.txt")


@pytest.mark.parametrize(
    "os,bits,processor,name",
    [
        ("linux", 32, "x86", "jsshell-linux-i686.zip"),
        ("linux", 64, "x86_64", "jsshell-linux-x86_64.zip"),
        ("mac", 64, "x86_64", "jsshell-mac.zip"),
        ("win", 32, "x86", "jsshell-win32.zip"),
        ("win", 64, "x86_64", "jsshell-win64.zip"),
        ("win", 64, "x86_64", "jsshell-win64-x86_64.zip"),
        ("win", 32, "aarch64", "jsshell-win32.zip"),
        ("win", 64, "aarch64", "jsshell-win64-aarch64.zip"),
    ],
)
def test_jsshell_build_regex(os, bits, processor, name):
    conf = create_config("jsshell", os, bits, processor)
    assert re.match(conf.build_regex(), name)


def test_jsshell_x86_64_build_regex():
    conf = create_config("jsshell", "win", 64, "x86_64")
    assert not re.match(conf.build_regex(), "jsshell-win64-aarch64.zip")


@pytest.mark.parametrize(
    "os,bits,processor,tc_suffix",
    [
        ("linux", 32, "x86", "linux-pgo"),
        ("linux", 64, "x86_64", "linux64-pgo"),
        ("mac", 64, "x86_64", errors.MozRegressionError),
        ("win", 32, "x86", "win32-pgo"),
        ("win", 64, "x86_64", "win64-pgo"),
    ],
)
def test_set_firefox_build_type_pgo(os, bits, processor, tc_suffix):
    conf = create_config("firefox", os, bits, processor)
    if type(tc_suffix) is not str:
        with pytest.raises(tc_suffix):
            conf.set_build_type("pgo")
    else:
        conf.set_build_type("pgo")
        assert conf.tk_route(create_push(CHSET, TIMESTAMP_TEST)).endswith("." + tc_suffix)


if __name__ == "__main__":
    unittest.main()
