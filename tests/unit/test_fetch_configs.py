import unittest
import datetime

from mozregression.fetch_configs import (FirefoxConfig, create_config)

class TestFirefoxConfigLinux64(unittest.TestCase):
    app_name = 'firefox'
    os = 'linux'
    bits = 64

    build_regex = r'firefox.*linux-x86_64\.tar.bz2$'
    build_info_regex = r'firefox.*linux-x86_64\.txt$'

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
        self.assertEqual(self.conf.build_regex(), self.build_regex)

    def test_build_info_regex(self):
        self.assertEqual(self.conf.build_info_regex(), self.build_info_regex)

    def test_nightly_base_repo_name(self):
        self.assertEqual(self.conf.nightly_base_repo_name, 'firefox')

    def test_nightly_inbound_branch(self):
        self.assertEqual(self.conf.nightly_inbound_branch(datetime.date(2008, 6, 15)), 'trunk')
        self.assertEqual(self.conf.nightly_inbound_branch(datetime.date(2008, 6, 27)), 'mozilla-central')

    def test_inbound_base_url(self):
        inbound_base_url = '%s/mozilla-inbound-%s/' % (self.base_inbound_url,
                                                      self.base_inbound_url_ext)
        self.assertEqual(self.conf.inbound_base_url(), inbound_base_url)

    def test_custom_inbound_base_url(self):
        self.conf.set_inbound_branch('custom')
        inbound_base_url = '%s/custom-%s/' % (self.base_inbound_url,
                                                      self.base_inbound_url_ext)
        self.assertEqual(self.conf.inbound_base_url(), inbound_base_url)

class TestFirefoxConfigLinux32(TestFirefoxConfigLinux64):
    bits = 32
    build_regex = r'firefox.*linux-i686\.tar.bz2$'
    build_info_regex = r'firefox.*linux-i686\.txt$'
    base_inbound_url_ext = 'linux'

class TestFirefoxConfigWin64(TestFirefoxConfigLinux64):
    os = 'win'
    build_regex = r'firefox.*win64-x86_64\.zip$'
    build_info_regex = r'firefox.*win64-x86_64\.txt$'
    base_inbound_url_ext = 'win64'

class TestFirefoxConfigWin32(TestFirefoxConfigWin64):
    bits = 32
    build_regex = r'firefox.*win32\.zip$'
    build_info_regex = r'firefox.*win32\.txt$'
    base_inbound_url_ext = 'win32'

class TestFirefoxConfigMac(TestFirefoxConfigLinux64):
    os = 'mac'
    build_regex = r'firefox.*mac.*\.dmg$'
    build_info_regex = r'firefox.*mac.*\.txt$'
    base_inbound_url_ext = 'macosx64'

if __name__ == '__main__':
    unittest.main()
