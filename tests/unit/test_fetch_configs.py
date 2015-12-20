import unittest
import datetime
import re
import pytest

from mozregression.fetch_configs import (FirefoxConfig, create_config, errors,
                                         get_build_regex, NIGHTLY_BASE_URL)


class TestFirefoxConfigLinux64(unittest.TestCase):
    app_name = 'firefox'
    os = 'linux'
    bits = 64

    build_examples = ['firefox-38.0a1.en-US.linux-x86_64.tar.bz2']
    build_info_examples = ['firefox-38.0a1.en-US.linux-x86_64.txt']

    instance_type = FirefoxConfig
    is_nightly = True
    is_inbound = True

    def setUp(self):
        self.conf = create_config(self.app_name, self.os, self.bits)

    def test_instance(self):
        self.assertIsInstance(self.conf, self.instance_type)
        self.assertEqual(self.is_nightly, self.conf.is_nightly())
        self.assertEqual(self.is_inbound, self.conf.is_inbound())

    def test_build_regex(self):
        for example in self.build_examples:
            res = re.match(self.conf.build_regex(), example)
            self.assertIsNotNone(res)

    def test_build_info_regex(self):
        for example in self.build_info_examples:
            res = re.match(self.conf.build_info_regex(), example)
            self.assertIsNotNone(res)

    def test_get_nighly_base_url(self):
        base_url = self.conf.get_nighly_base_url(datetime.date(2008,
                                                               6, 27))
        self.assertEqual(base_url,
                         NIGHTLY_BASE_URL + '/firefox/nightly/2008/06/')

    def test_nightly_repo_regex(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 15))
        self.assertEqual(repo_regex, '^2008-06-15-[\\d-]+trunk/$')
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 27))
        self.assertEqual(repo_regex, '^2008-06-27-[\\d-]+mozilla-central/$')
        # test with a datetime instance (buildid)
        repo_regex = self.conf.get_nightly_repo_regex(
            datetime.datetime(2015, 11, 27, 6, 5, 58))
        self.assertEqual(repo_regex, '^2015-11-27-06-05-58-mozilla-central/$')

    def test_set_repo(self):
        self.conf.set_repo('foo-bar')
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 27))
        self.assertEqual(repo_regex, '^2008-06-27-[\\d-]+foo-bar/$')
        # with a value of None, default is applied
        self.conf.set_repo(None)
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 27))
        self.assertEqual(repo_regex, '^2008-06-27-[\\d-]+mozilla-central/$')

    def test_can_go_inbound(self):
        self.assertTrue(self.conf.can_go_inbound())


class TestFirefoxConfigLinux32(TestFirefoxConfigLinux64):
    bits = 32
    build_examples = ['firefox-38.0a1.en-US.linux-i686.tar.bz2']
    build_info_examples = ['firefox-38.0a1.en-US.linux-i686.txt']


class TestFirefoxConfigWin64(TestFirefoxConfigLinux64):
    os = 'win'
    build_examples = ['firefox-38.0a1.en-US.win64-x86_64.zip',
                      'firefox-38.0a1.en-US.win64.zip']
    build_info_examples = ['firefox-38.0a1.en-US.win64-x86_64.txt',
                           'firefox-38.0a1.en-US.win64.txt']


class TestFirefoxConfigWin32(TestFirefoxConfigWin64):
    bits = 32
    build_examples = ['firefox-38.0a1.en-US.win32.zip']
    build_info_examples = ['firefox-38.0a1.en-US.win32.txt']


class TestFirefoxConfigMac(TestFirefoxConfigLinux64):
    os = 'mac'
    build_examples = ['firefox-38.0a1.en-US.mac.dmg']
    build_info_examples = ['firefox-38.0a1.en-US.mac.txt']


class TestThunderbirdConfig(unittest.TestCase):
    os = 'linux'
    bits = 64

    def setUp(self):
        self.conf = create_config('thunderbird', self.os, self.bits)

    def test_nightly_repo_regex_before_2008_07_26(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    7, 25))
        self.assertEqual(repo_regex, '^2008-07-25-[\\d-]+trunk/$')

    def test_nightly_repo_regex_before_2009_01_09(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2009,
                                                                    1, 8))
        self.assertEqual(repo_regex, '^2009-01-08-[\\d-]+comm-central/$')

    def test_nightly_repo_regex_before_2010_08_21(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2010,
                                                                    8, 20))
        self.assertEqual(repo_regex, '^2010-08-20-[\\d-]+comm-central-trunk/$')

    def test_nightly_repo_regex_since_2010_08_21(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2010,
                                                                    8, 21))
        self.assertEqual(repo_regex, '^2010-08-21-[\\d-]+comm-central/$')


class TestThunderbirdConfigWin(TestThunderbirdConfig):
    os = 'win'

    def test_nightly_repo_regex_before_2008_07_26(self):
        with self.assertRaises(errors.WinTooOldBuildError):
            TestThunderbirdConfig.\
                test_nightly_repo_regex_before_2008_07_26(self)

    def test_nightly_repo_regex_before_2009_01_09(self):
        with self.assertRaises(errors.WinTooOldBuildError):
            TestThunderbirdConfig.\
                test_nightly_repo_regex_before_2009_01_09(self)


class TestFennecConfig(unittest.TestCase):
    def setUp(self):
        self.conf = create_config('fennec', 'linux', 64)

    def test_get_nightly_repo_regex(self):
        regex = self.conf.get_nightly_repo_regex(datetime.date(2014,
                                                               12, 5))
        self.assertIn("mozilla-central-android", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2014,
                                                               12, 10))
        self.assertIn("mozilla-central-android-api-10", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2015,
                                                               1, 1))
        self.assertIn("mozilla-central-android-api-11", regex)

    def test_build_regex(self):
        regex = re.compile(self.conf.build_regex())
        self.assertTrue(regex.match('fennec-36.0a1.multi.android-arm.apk'))

    def test_build_info_regex(self):
        regex = re.compile(self.conf.build_info_regex())
        self.assertTrue(regex.match('fennec-36.0a1.multi.android-arm.txt'))


class TestFennec23Config(unittest.TestCase):
    def setUp(self):
        self.conf = create_config('fennec-2.3', 'linux', 64)

    def test_class_attr_name(self):
        self.assertEqual(self.conf.app_name, 'fennec')

    def test_get_nightly_repo_regex(self):
        regex = self.conf.get_nightly_repo_regex(datetime.date(2014, 12, 5))
        self.assertIn("mozilla-central-android", regex)
        regex = self.conf.get_nightly_repo_regex(datetime.date(2015, 1, 1))
        self.assertIn("mozilla-central-android-api-9", regex)


class TestB2GConfig(unittest.TestCase):
    def setUp(self):
        self.conf = create_config('b2g', 'linux', 64)

    def test_get_nightly_repo(self):
        repo = self.conf.get_nightly_repo(datetime.date(2014, 12, 5))
        self.assertEqual(repo, "mozilla-central")


class TestGetBuildUrl(unittest.TestCase):
    def test_for_linux(self):
        self.assertEqual(get_build_regex('test', 'linux', 32),
                         r'test.*linux-i686\.tar.bz2')

        self.assertEqual(get_build_regex('test', 'linux', 64),
                         r'test.*linux-x86_64\.tar.bz2')

        self.assertEqual(get_build_regex('test', 'linux', 64,
                                         with_ext=False),
                         r'test.*linux-x86_64')

    def test_for_win(self):
        self.assertEqual(get_build_regex('test', 'win', 32),
                         r'test.*win32\.zip')
        self.assertEqual(get_build_regex('test', 'win', 64),
                         r'test.*win64(-x86_64)?\.zip')
        self.assertEqual(get_build_regex('test', 'win', 64,
                                         with_ext=False),
                         r'test.*win64(-x86_64)?')

    def test_for_mac(self):
        self.assertEqual(get_build_regex('test', 'mac', 32),
                         r'test.*mac.*\.dmg')
        self.assertEqual(get_build_regex('test', 'mac', 64),
                         r'test.*mac.*\.dmg')
        self.assertEqual(get_build_regex('test', 'mac', 64,
                                         with_ext=False),
                         r'test.*mac.*')

    def test_unknown_os(self):
        with self.assertRaises(errors.MozRegressionError):
            get_build_regex('test', 'unknown', 32)


CHSET = "47856a21491834da3ab9b308145caa8ec1b98ee1"
CHSET12 = "47856a214918"


@pytest.mark.parametrize("app,os,bits,expected", [
    # firefox
    ("firefox", 'linux', 32,
     'buildbot.revisions.%s.mozilla-inbound.linux' % CHSET),
    ("firefox", 'linux', 64,
     'buildbot.revisions.%s.mozilla-inbound.linux64' % CHSET),
    ("firefox", 'win', 32,
     'buildbot.revisions.%s.mozilla-inbound.win32' % CHSET),
    ("firefox", 'win', 64,
     'buildbot.revisions.%s.mozilla-inbound.win64' % CHSET),
    ("firefox", 'mac', 64,
     'buildbot.revisions.%s.mozilla-inbound.macosx64' % CHSET),
    # fennec
    ("fennec", None, None,
     'buildbot.revisions.%s.mozilla-inbound.android-api-11' % CHSET),
    ("fennec-2.3", None, None,
     'buildbot.revisions.%s.mozilla-inbound.android-api-9' % CHSET),
    # b2g
    ("b2g", 'linux', 32,
     'buildbot.revisions.%s.b2g-inbound.linux_gecko' % CHSET),
    ("b2g", 'linux', 64,
     'buildbot.revisions.%s.b2g-inbound.linux64_gecko' % CHSET),
    ("b2g", 'win', 32,
     'buildbot.revisions.%s.b2g-inbound.win32_gecko' % CHSET12),
    ("b2g", 'win', 64,
     'buildbot.revisions.%s.b2g-inbound.win64_gecko' % CHSET12),
    ("b2g", 'mac', 64,
     'buildbot.revisions.%s.b2g-inbound.macosx64_gecko' % CHSET12),
])
def test_tk_inbound_route(app, os, bits, expected):
    conf = create_config(app, os, bits)
    result = conf.tk_inbound_route(CHSET)
    assert result == expected


@pytest.mark.parametrize("app,os,bits,build_type,expected", [
    # firefox
    ("firefox", 'linux', 32, "debug",
     'buildbot.revisions.%s.mozilla-inbound.linux-debug' % CHSET),
    # b2g-aries
    ("b2g-aries", None, None, "opt,eng",
     'gecko.v2.b2g-inbound.revision.%s.b2g.aries-eng-opt' % CHSET),
    # b2g-flame
    ("b2g-flame", None, None, "opt,spark,eng",
     'gecko.v2.b2g-inbound.revision.%s.b2g.flame-kk-spark-eng-opt' % CHSET),
    ("b2g-flame", None, None, "opt,spark,eng,kk",  # allow kk
     'gecko.v2.b2g-inbound.revision.%s.b2g.flame-kk-spark-eng-opt' % CHSET),
    # b2g-emulator
    ("b2g-emulator", None, None, "debug,jb",
     'gecko.v2.b2g-inbound.revision.%s.b2g.emulator-jb-debug' % CHSET),
])
def test_tk_inbound_route_with_build_type(app, os, bits, build_type, expected):
    conf = create_config(app, os, bits)
    conf.set_build_type(build_type)
    result = conf.tk_inbound_route(CHSET)
    assert result == expected


def test_set_build_type():
    conf = create_config('firefox', 'linux', 64)
    assert conf.build_type == 'opt'  # default is opt
    conf.set_build_type('debug')
    assert conf.build_type == 'debug'


def test_set_bad_build_type():
    conf = create_config('firefox', 'linux', 64)
    with pytest.raises(errors.MozRegressionError):
        conf.set_build_type("wrong build type")


def test_cant_set_debug_build_type_for_b2g():
    conf = create_config('b2g', 'linux', 64)
    with pytest.raises(errors.MozRegressionError):
        conf.set_build_type("debug")


def test_jsshell_build_info_regex():
    conf = create_config('jsshell', 'linux', 64)
    assert re.match(conf.build_info_regex(),
                    'firefox-38.0a1.en-US.linux-x86_64.txt')


@pytest.mark.parametrize('os,bits,name', [
    ('linux', 32, 'jsshell-linux-i686.zip'),
    ('linux', 64, 'jsshell-linux-x86_64.zip'),
    ('mac', 64, 'jsshell-mac.zip'),
    ('win', 32, 'jsshell-win32.zip'),
    ('win', 64, 'jsshell-win64.zip'),
])
def test_jsshell_build_regex(os, bits, name):
    conf = create_config('jsshell', os, bits)
    assert re.match(conf.build_regex(), name)


@pytest.mark.parametrize('appname,build_type,persist_part', [
    ('firefox', 'opt', ''),
    ('firefox', 'debug', 'debug'),
    ('jsshell', 'opt', ''),
    ('jsshell', 'debug', 'debug'),
    ('fennec', 'opt', ''),
])
def test_nightly_handle_build_type(appname, build_type, persist_part):
    conf = create_config(appname, 'linux', 64)
    conf.set_build_type(build_type)
    assert conf.nightly_persist_part() == persist_part
    assert conf.nightly_handle_build_type()


@pytest.mark.parametrize('appname,build_type,date,branch,match_sample', [
    ('firefox', 'debug', datetime.date(2014, 8, 1), 'mozilla-central',
     '2014-08-01-mozilla-central-debug/'),
    ('firefox', 'debug', datetime.date(2014, 8, 1), 'aurora',
     '2014-08-01-mozilla-aurora-debug/'),
])
def test_get_nightly_repo_regex_with_build_type(appname, build_type, date,
                                                branch, match_sample):
    conf = create_config(appname, 'linux', 64)
    conf.set_build_type(build_type)
    conf.set_repo(branch)
    assert re.match(conf.get_nightly_repo_regex(date), match_sample)

if __name__ == '__main__':
    unittest.main()
