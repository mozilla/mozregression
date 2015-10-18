import unittest

from mozregression import errors
from mozregression.releases import (releases, formatted_valid_release_dates,
                                    date_of_release)


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
