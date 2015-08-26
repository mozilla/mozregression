#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
import tempfile
import os
import datetime
import pytest

from mock import patch

from mozregression import cli, errors
from mozregression.releases import releases


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


class TestPreferences(unittest.TestCase):
    def test_preferences_file(self):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('{ "browser.tabs.remote.autostart": false }')

        prefs_files = [filepath]
        prefs = cli.preferences(prefs_files, None)
        self.assertEqual(prefs, [('browser.tabs.remote.autostart', False)])

    def test_preferences_args(self):
        prefs_args = ["browser.tabs.remote.autostart:false"]

        prefs = cli.preferences(None, prefs_args)
        self.assertEqual(prefs, [('browser.tabs.remote.autostart', False)])

        prefs_args = ["browser.tabs.remote.autostart"]

        prefs = cli.preferences(None, prefs_args)
        self.assertEquals(len(prefs), 0)


class TestCli(unittest.TestCase):

    def test_get_erronous_cfg_defaults(self):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write('aaaaaaaaaaa [Defaults]\n')

        with self.assertRaises(errors.MozRegressionError):
            cli.cli(conf_file=filepath)

    def test_get_defaults(self):
        valid_values = {'http-timeout': '10.2',
                        'persist': '/home/foo/.mozregression',
                        'bits': '64'}

        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            for key, value in valid_values.iteritems():
                conf_file.write("%s=%s\n" % (key, value))

        options = cli.cli(['--bits=32'], conf_file=filepath).options

        self.assertEqual(options.http_timeout, 10.2)
        self.assertEqual(options.persist, '/home/foo/.mozregression')
        self.assertEqual(options.bits, '32')


def do_cli(*argv):
    conf = cli.cli(argv, conf_file=None)
    conf.validate()
    return conf


def test_get_usage():
    output = []
    with patch('sys.stdout') as stdout:
        stdout.write.side_effect = output.append

        with pytest.raises(SystemExit) as exc:
            do_cli('-h')
    assert exc.value.code == 0
    assert "usage:" in ''.join(output)


DEFAULTS_DATE = [
    ('linux', 64, datetime.date(2009, 1, 1)),
    ('linux', 32, datetime.date(2009, 1, 1)),
    ('mac', 64, datetime.date(2009, 1, 1)),
    ('win', 32, datetime.date(2009, 1, 1)),
    ('win', 64, datetime.date(2010, 5, 28)),
]


@pytest.mark.parametrize("os,bits,default_good_date", DEFAULTS_DATE)
def test_no_args(os, bits, default_good_date):
    with patch('mozregression.cli.mozinfo') as mozinfo:
        mozinfo.os = os
        mozinfo.bits = bits
        config = do_cli()
        # application is by default firefox
        assert config.fetch_config.app_name == 'firefox'
        # nightly by default
        assert config.action == 'bisect_nightlies'
        assert config.options.good_date == default_good_date
        assert config.options.bad_date == datetime.date.today()


@pytest.mark.parametrize("os,bits,default_bad_date", DEFAULTS_DATE)
def test_find_fix_reverse_default_dates(os, bits, default_bad_date):
    with patch('mozregression.cli.mozinfo') as mozinfo:
        mozinfo.os = os
        mozinfo.bits = bits
        config = do_cli('--find-fix')
        # application is by default firefox
        assert config.fetch_config.app_name == 'firefox'
        # nightly by default
        assert config.action == 'bisect_nightlies'
        assert config.options.bad_date == default_bad_date
        assert config.options.good_date == datetime.date.today()


@pytest.mark.parametrize('arg1,arg2', [
    ['--bad-release=31', '--bad=2015-01-01'],
    ['--good-release=31', '--good=2015-01-01']
])
def test_date_release_are_incompatible(arg1, arg2):
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli(arg1, arg2)
    assert 'incompatible' in str(exc.value)


def test_with_releases():
    releases_data = sorted(((k, v) for k, v in releases().items()),
                           key=(lambda (k, v): k))
    conf = do_cli(
        '--bad-release=%s' % releases_data[-1][0],
        '--good-release=%s' % releases_data[0][0],
    )
    assert str(conf.options.good_date) == releases_data[0][1]
    assert str(conf.options.bad_date) == releases_data[-1][1]


def test_bad_date_later_than_good():
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli('--good=2015-01-01', '--bad=2015-01-10', '--find-fix')
    assert 'is later than good' in str(exc.value)
    assert "You should not use the --find-fix" in str(exc.value)


def test_good_date_later_than_bad():
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli('--good=2015-01-10', '--bad=2015-01-01')
    assert 'is later than bad' in str(exc.value)
    assert "you wanted to use the --find-fix" in str(exc.value)


def test_basic_inbound():
    config = do_cli('--good-rev=1', '--bad-rev=5')
    assert config.fetch_config.app_name == 'firefox'
    assert config.action == 'bisect_inbounds'
    assert config.options.last_good_revision == '1'
    assert config.options.first_bad_revision == '5'


@pytest.mark.parametrize('arg', ['--good-rev=1', '--bad-rev=5'])
def test_both_inbound_revs_must_be_given(arg):
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli(arg)
    assert '--good-rev and --bad-rev must be set' in str(exc.value)


def test_inbound_must_be_doable():
    # no inbounds for thunderbird
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli('--app', 'thunderbird', '--good-rev=1', '--bad-rev=5')
        assert 'Unable to bissect inbound' in str(exc.value)


def test_list_releases(mocker):
    out = []
    stdout = mocker.patch('sys.stdout')
    stdout.write = out.append
    with pytest.raises(SystemExit):
        do_cli('--list-releases')
    assert 'Valid releases:' in '\n'.join(out)


def test_write_confif(mocker):
    out = []
    stdout = mocker.patch('sys.stdout')
    stdout.write = out.append
    write_conf = mocker.patch('mozregression.cli.write_conf')
    with pytest.raises(SystemExit):
        do_cli('--write-conf')
    assert len(write_conf.mock_calls) == 1


def test_warning_no_conf(mocker):
    out = []
    stdout = mocker.patch('sys.stdout')
    stdout.write = out.append
    cli.cli([], conf_file='blah_this is not a valid file_I_hope')
    assert "You should use a config file" in '\n'.join(out)
