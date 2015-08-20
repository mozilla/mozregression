#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
import tempfile
import os
import datetime

from mock import patch

from mozregression import cli, errors


class TestParseDate(unittest.TestCase):
    def test_valid_date(self):
        date = cli.parse_date("2014-07-05")
        self.assertEquals(date, datetime.date(2014, 7, 5))

    def test_invalid_date(self):
        self.assertRaises(errors.DateFormatError, cli.parse_date,
                          "invalid_format")


class TestParseBits(unittest.TestCase):
    @patch('mozregression.cli.mozinfo')
    def test_parse_32(self, mozinfo):
        mozinfo.bits = 32
        self.assertEqual(cli.parse_bits('32'), 32)
        self.assertEqual(cli.parse_bits('64'), 32)

    @patch('mozregression.cli.mozinfo')
    def test_parse_64(self, mozinfo):
        mozinfo.bits = 64
        self.assertEqual(cli.parse_bits('32'), 32)
        self.assertEqual(cli.parse_bits('64'), 64)


class TestRelease(unittest.TestCase):
    def test_valid_release_to_date(self):
        date = cli.date_of_release(8)
        self.assertEquals(date, "2011-08-16")
        date = cli.date_of_release(15)
        self.assertEquals(date, "2012-06-05")
        date = cli.date_of_release(34)
        self.assertEquals(date, "2014-09-02")

    def test_valid_formatted_release_dates(self):
        formatted_output = cli.formatted_valid_release_dates()
        firefox_releases = cli.releases()

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
            cli.date_of_release(4)
        with self.assertRaises(errors.UnavailableRelease):
            cli.date_of_release(441)


class TestMainCli(unittest.TestCase):

    def test_get_erronous_cfg_defaults(self):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('aaaaaaaaaaa [Defaults]\n')

        with self.assertRaises(SystemExit):
            cli.get_defaults(filepath)

    def test_get_defaults(self):
        valid_values = {'http-timeout': '10.2',
                        'persist': '/home/foo/.mozregression',
                        'bits': '64'}

        handle, filepath = tempfile.mkstemp()
        conf_default = cli.DEFAULT_CONF_FNAME

        self.addCleanup(os.unlink, filepath)
        self.addCleanup(setattr, cli, "DEFAULT_CONF_FNAME", conf_default)

        cli.DEFAULT_CONF_FNAME = filepath

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('[Defaults]\n')
            for key, value in valid_values.iteritems():
                conf_file.write("%s=%s\n" % (key, value))

        options = cli.parse_args(['--bits=32'])

        self.assertEqual(options.http_timeout, 10.2)
        self.assertEqual(options.persist, '/home/foo/.mozregression')
        self.assertEqual(options.bits, '32')

if __name__ == '__main__':
    unittest.main()
