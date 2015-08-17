import unittest
from mock import patch
import datetime
from mozregression import utils, errors


class TestParseDate(unittest.TestCase):
    def test_valid_date(self):
        date = utils.parse_date("2014-07-05")
        self.assertEquals(date, datetime.date(2014, 7, 5))

    def test_invalid_date(self):
        self.assertRaises(errors.DateFormatError, utils.parse_date,
                          "invalid_format")


class TestParseBits(unittest.TestCase):
    @patch('mozregression.utils.mozinfo')
    def test_parse_32(self, mozinfo):
        mozinfo.bits = 32
        self.assertEqual(utils.parse_bits('32'), 32)
        self.assertEqual(utils.parse_bits('64'), 32)

    @patch('mozregression.utils.mozinfo')
    def test_parse_64(self, mozinfo):
        mozinfo.bits = 64
        self.assertEqual(utils.parse_bits('32'), 32)
        self.assertEqual(utils.parse_bits('64'), 64)


class TestRelease(unittest.TestCase):
    def test_valid_release_to_date(self):
        date = utils.date_of_release(8)
        self.assertEquals(date, "2011-08-16")
        date = utils.date_of_release(15)
        self.assertEquals(date, "2012-06-05")
        date = utils.date_of_release(34)
        self.assertEquals(date, "2014-09-02")

    def test_valid_formatted_release_dates(self):
        formatted_output = utils.formatted_valid_release_dates()
        firefox_releases = utils.releases()

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
            utils.date_of_release(4)
        with self.assertRaises(errors.UnavailableRelease):
            utils.date_of_release(441)


if __name__ == '__main__':
    unittest.main()
