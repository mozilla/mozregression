import unittest

from mozregression import errors
from mozregression.releases import (releases, formatted_valid_release_dates,
                                    date_of_release, tag_of_release,
                                    tag_of_beta)


class TestRelease(unittest.TestCase):
    def test_valid_release_to_date(self):
        date = date_of_release(8)
        self.assertEquals(date, "2011-08-16")
        date = date_of_release(15)
        self.assertEquals(date, "2012-06-05")
        date = date_of_release(34)
        self.assertEquals(date, "2014-09-02")
        date = date_of_release('33')
        self.assertEquals(date, "2014-07-21")

    def test_valid_formatted_release_dates(self):
        formatted_output = formatted_valid_release_dates()
        firefox_releases = releases()

        for line in formatted_output.splitlines():
            if "Valid releases: " in line:
                continue

            fields = line.translate(None, " ").split(":")
            version = int(fields[0])
            date = fields[1]

            self.assertTrue(version in firefox_releases)
            self.assertEquals(date, firefox_releases[version])

    def test_invalid_release_to_date(self):
        with self.assertRaises(errors.UnavailableRelease):
            date_of_release(4)
        with self.assertRaises(errors.UnavailableRelease):
            date_of_release(441)
        with self.assertRaises(errors.UnavailableRelease):
            date_of_release('ew21rtw112')

    def test_valid_release_tags(self):
        tag = tag_of_release('57.0')
        self.assertEquals(tag, "FIREFOX_57_0_RELEASE")
        tag = tag_of_release('60')
        self.assertEquals(tag, "FIREFOX_60_0_RELEASE")
        tag = tag_of_release('65.0.1')
        self.assertEquals(tag, "FIREFOX_65_0_1_RELEASE")

    def test_invalid_release_tags(self):
        with self.assertRaises(errors.UnavailableRelease):
            tag_of_release('55.0.1.1')
        with self.assertRaises(errors.UnavailableRelease):
            tag_of_release('57.0b4')
        with self.assertRaises(errors.UnavailableRelease):
            tag_of_release('abc')

    def test_valid_beta_tags(self):
        tag = tag_of_beta('57.0b9')
        self.assertEquals(tag, "FIREFOX_57_0b9_RELEASE")
        tag = tag_of_beta('60.0b12')
        self.assertEquals(tag, "FIREFOX_60_0b12_RELEASE")
        tag = tag_of_beta('65')
        self.assertEquals(tag, "FIREFOX_RELEASE_65_BASE")
        tag = tag_of_beta('66.0')
        self.assertEquals(tag, "FIREFOX_RELEASE_66_BASE")

    def test_invalid_beta_tags(self):
        with self.assertRaises(errors.UnavailableRelease):
            tag_of_beta('57.0.1')
        with self.assertRaises(errors.UnavailableRelease):
            tag_of_beta('xyz')
