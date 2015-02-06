import unittest
import datetime
import re

from mozregression.fetch_configs import (FirefoxConfig, create_config, errors)


class TestFirefoxConfigLinux64(unittest.TestCase):
    app_name = 'firefox'
    os = 'linux'
    bits = 64

    build_examples = ['firefox-38.0a1.en-US.linux-x86_64.tar.bz2']
    build_info_examples = ['firefox-38.0a1.en-US.linux-x86_64.txt']

    instance_type = FirefoxConfig
    is_nightly = True
    is_inbound = True

    base_inbound_url = ('http://inbound-archive.pub.build.mozilla.org/pub/'
                        'mozilla.org/firefox/tinderbox-builds')
    base_inbound_url_ext = 'linux64'

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
        self.assertEqual(base_url, 'http://ftp.mozilla.org/pub/mozilla.org/\
firefox/nightly/2008/06/')

    def test_nightly_repo_regex(self):
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 15))
        self.assertEqual(repo_regex, '^2008-06-15-[\\d-]+trunk/$')
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 27))
        self.assertEqual(repo_regex, '^2008-06-27-[\\d-]+mozilla-central/$')

    def test_set_nightly_repo(self):
        self.conf.set_nightly_repo('foo-bar')
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 27))
        self.assertEqual(repo_regex, '^2008-06-27-[\\d-]+foo-bar/$')
        # with a value of None, default is applied
        self.conf.set_nightly_repo(None)
        repo_regex = self.conf.get_nightly_repo_regex(datetime.date(2008,
                                                                    6, 27))
        self.assertEqual(repo_regex, '^2008-06-27-[\\d-]+mozilla-central/$')

    def test_can_go_inbound(self):
        self.assertTrue(self.conf.can_go_inbound())
        # if nightly_repo is set, we can not bissect inbound
        self.conf.set_nightly_repo('foo-bar')
        self.assertFalse(self.conf.can_go_inbound())

    def test_inbound_base_urls(self):
        inbound_base_url = '%s/mozilla-inbound-%s/' % \
            (self.base_inbound_url, self.base_inbound_url_ext)

        self.assertEqual(self.conf.inbound_base_urls(), [inbound_base_url])

    def test_custom_inbound_base_urls(self):
        self.conf.set_inbound_branch('custom')
        inbound_base_url = '%s/custom-%s/' % (self.base_inbound_url,
                                              self.base_inbound_url_ext)
        self.assertEqual(self.conf.inbound_base_urls(), [inbound_base_url])


class TestFirefoxConfigLinux32(TestFirefoxConfigLinux64):
    bits = 32
    build_examples = ['firefox-38.0a1.en-US.linux-i686.tar.bz2']
    build_info_examples = ['firefox-38.0a1.en-US.linux-i686.txt']
    base_inbound_url_ext = 'linux'


class TestFirefoxConfigWin64(TestFirefoxConfigLinux64):
    os = 'win'
    build_examples = ['firefox-38.0a1.en-US.win64-x86_64.zip',
                      'firefox-38.0a1.en-US.win64.zip']
    build_info_examples = ['firefox-38.0a1.en-US.win64-x86_64.txt',
                           'firefox-38.0a1.en-US.win64.txt']
    base_inbound_url_ext = 'win64'


class TestFirefoxConfigWin32(TestFirefoxConfigWin64):
    bits = 32
    build_examples = ['firefox-38.0a1.en-US.win32.zip']
    build_info_examples = ['firefox-38.0a1.en-US.win32.txt']
    base_inbound_url_ext = 'win32'


class TestFirefoxConfigMac(TestFirefoxConfigLinux64):
    os = 'mac'
    build_examples = ['firefox-38.0a1.en-US.mac.dmg']
    build_info_examples = ['firefox-38.0a1.en-US.mac.txt']
    base_inbound_url_ext = 'macosx64'


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

    def test_get_nightly_repo(self):
        repo = self.conf.get_nightly_repo(datetime.date(2014,
                                                        12, 5))
        self.assertEqual(repo, "mozilla-central-android")
        repo = self.conf.get_nightly_repo(datetime.date(2014,
                                                        12, 10))
        self.assertEqual(repo, "mozilla-central-android-api-10")
        repo = self.conf.get_nightly_repo(datetime.date(2015,
                                                        1, 1))
        self.assertEqual(repo, "mozilla-central-android-api-11")

    def test_build_regex(self):
        regex = re.compile(self.conf.build_regex())
        self.assertTrue(regex.match('fennec-36.0a1.multi.android-arm.apk'))

    def test_build_info_regex(self):
        regex = re.compile(self.conf.build_info_regex())
        self.assertTrue(regex.match('fennec-36.0a1.multi.android-arm.txt'))

    def test_inbound_base_url(self):
        expected = ["http://inbound-archive.pub.build.mozilla.org\
/pub/mozilla.org"
                    "/mobile/tinderbox-builds/%s/" % inbound_branch
                    for inbound_branch in ('mozilla-inbound-android',
                                           'mozilla-inbound-android-api-10',
                                           'mozilla-inbound-android-api-11')]
        self.assertEqual(self.conf.inbound_base_urls(), expected)

    def test_set_inbound_branch(self):
        # inbound_branch evaluated to False won't change the behaviour
        self.conf.set_inbound_branch(None)
        self.test_inbound_base_url()

        # valid inbound_branch will
        self.conf.set_inbound_branch('my')
        expected = ["http://inbound-archive.pub.build.mozilla.org/\
pub/mozilla.org"
                    "/mobile/tinderbox-builds/my/"]
        self.assertEqual(self.conf.inbound_base_urls(), expected)


class TestFennec23Config(unittest.TestCase):
    def setUp(self):
        self.conf = create_config('fennec-2.3', 'linux', 64)

    def test_class_attr_name(self):
        self.assertEqual(self.conf.app_name, 'fennec')

    def test_get_nightly_repo(self):
        repo = self.conf.get_nightly_repo(datetime.date(2014, 12, 5))
        self.assertEqual(repo, "mozilla-central-android")
        repo = self.conf.get_nightly_repo(datetime.date(2015, 1, 1))
        self.assertEqual(repo, "mozilla-central-android-api-9")


class TestB2GConfig(unittest.TestCase):
    def setUp(self):
        self.conf = create_config('b2g', 'linux', 64)

    def test_get_nightly_repo(self):
        repo = self.conf.get_nightly_repo(datetime.date(2014, 12, 5))
        self.assertEqual(repo, "mozilla-central")

if __name__ == '__main__':
    unittest.main()
