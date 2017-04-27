# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import unittest
import tempfile
import os
import datetime
import pytest

from mock import patch
from mozlog import get_default_logger

from mozregression import cli, errors
from mozregression.releases import releases
from mozregression.fetch_configs import create_config


class TestParseDate(unittest.TestCase):
    def test_valid_date(self):
        date = cli.parse_date("2014-07-05")
        self.assertEquals(date, datetime.date(2014, 7, 5))

    def test_parse_buildid(self):
        date = cli.parse_date("20151103030248")
        self.assertEquals(date, datetime.datetime(2015, 11, 3, 3, 2, 48))

    def test_invalid_date(self):
        self.assertRaises(errors.DateFormatError, cli.parse_date,
                          "invalid_format")
        # test invalid buildid (43 is not a valid day)
        self.assertRaises(errors.DateFormatError, cli.parse_date,
                          "20151143030248")


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
    def _create_conf_file(self, content):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, 'w') as conf_file:
            conf_file.write(content)
        return filepath

    def test_get_erronous_cfg_defaults(self):
        filepath = self._create_conf_file('aaaaaaaaaaa [Defaults]\n')

        with self.assertRaises(errors.MozRegressionError):
            cli.cli(conf_file=filepath)

    def test_get_defaults(self):
        valid_values = {'http-timeout': '10.2',
                        'persist': '/home/foo/.mozregression',
                        'bits': '64'}

        content = ["%s=%s\n" % (key, value)
                   for key, value in valid_values.iteritems()]
        filepath = self._create_conf_file('\n'.join(content))

        options = cli.cli(['--bits=32'], conf_file=filepath).options

        self.assertEqual(options.http_timeout, 10.2)
        self.assertEqual(options.persist, '/home/foo/.mozregression')
        self.assertEqual(options.bits, '32')

    def test_warn_invalid_build_type_in_conf(self):
        filepath = self._create_conf_file('build-type=foo\n')
        conf = cli.cli([], conf_file=filepath)
        warns = []
        conf.logger.warning = warns.append
        conf.validate()
        self.assertIn(
            "Unable to find a suitable build type 'foo'."
            " (Defaulting to 'opt')",
            warns
        )


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


def test_list_build_types(mocker):
    output = []
    with patch('sys.stdout') as stdout:
        stdout.write.side_effect = output.append

        with pytest.raises(SystemExit) as exc:
            do_cli('--list-build-types')
    assert exc.value.code == 0
    assert "firefox:\n  opt" in ''.join(output)


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
        assert config.options.good == default_good_date
        assert config.options.bad == datetime.date.today()


TODAY = datetime.date.today()
SOME_DATE = TODAY + datetime.timedelta(days=-20)
SOME_OLDER_DATE = TODAY + datetime.timedelta(days=-10)


@pytest.mark.parametrize('params,good,bad', [
    # we can use dates with integration branches
    (['--good=%s' % SOME_DATE, '--bad=%s' % SOME_OLDER_DATE, '--repo=m-i'],
     SOME_DATE, SOME_OLDER_DATE),
    # non opt build flavors are also found using taskcluster
    (['--good=%s' % SOME_DATE, '--bad=%s' % SOME_OLDER_DATE, '-B', 'debug'],
     SOME_DATE, SOME_OLDER_DATE)
])
def test_use_taskcluster_bisection_method(params, good, bad):
    config = do_cli(*params)

    assert config.action == 'bisect_inbounds'  # meaning taskcluster usage
    # compare dates using the representation, as we may have
    # date / datetime instances
    assert config.options.good.strftime('%Y-%m-%d') \
        == good.strftime('%Y-%m-%d')
    assert config.options.bad.strftime('%Y-%m-%d') \
        == bad.strftime('%Y-%m-%d')


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
        assert config.options.bad == default_bad_date
        assert config.options.good == datetime.date.today()


def test_with_releases():
    releases_data = sorted(((k, v) for k, v in releases().items()),
                           key=(lambda (k, v): k))
    conf = do_cli(
        '--bad=%s' % releases_data[-1][0],
        '--good=%s' % releases_data[0][0],
    )
    assert str(conf.options.good) == releases_data[0][1]
    assert str(conf.options.bad) == releases_data[-1][1]


@pytest.mark.parametrize('args,action,value', [
    (['--launch=34'], 'launch_nightlies', cli.parse_date(releases()[34])),
    (['--launch=2015-11-01'], 'launch_nightlies', datetime.date(2015, 11, 1)),
    (['--launch=abc123'], 'launch_inbound', 'abc123'),
    (['--launch=2015-11-01', '--repo=m-i'], 'launch_inbound',
     datetime.date(2015, 11, 1)),
])
def test_launch(args, action, value):
    config = do_cli(*args)
    assert config.action == action
    assert config.options.launch == value


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
    config = do_cli('--good=c1', '--bad=c5')
    assert config.fetch_config.app_name == 'firefox'
    assert config.action == 'bisect_inbounds'
    assert config.options.good == 'c1'
    assert config.options.bad == 'c5'


def test_inbound_must_be_doable():
    # no inbounds for thunderbird
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli('--app', 'thunderbird', '--good=c1', '--bad=c5')
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


@pytest.mark.parametrize('args,enabled', [
    ([], False),  # not enabled by default, because build_type is opt
    (['-P=stdout'], True),  # explicitly enabled
    (['-B=debug'], True),  # enabled because build type is not opt
    (['-B=debug', '-P=none'], False),  # explicitly disabled
])
def test_process_output_enabled(args, enabled):
    do_cli(*args)
    log_filter = get_default_logger("process").component_filter

    result = log_filter({'some': 'data'})
    if enabled:
        assert result
    else:
        assert not result


@pytest.mark.parametrize('mozversion_msg,shown', [
    ("platform_changeset: abc123", False),
    ("application_changeset: abc123", True),
    ("application_version: stuff:thing", True),
    ("application_remotingname: stuff", False),
    ("application_id: stuff", False),
    ("application_vendor: stuff", False),
    ("application_display_name: stuff", False),
    ("not a valid key value pair", True),
])
def test_mozversion_output_filtered(mozversion_msg, shown):
    do_cli()
    log_filter = get_default_logger("mozversion").component_filter
    log_data = {'message': mozversion_msg}

    result = log_filter(log_data)
    if shown:
        assert result == log_data
    else:
        assert not result


@pytest.mark.parametrize('app, os, bits, build_type, expected_range', [
    ('jsshell', 'win', 64, None, (datetime.date(2014, 5, 27), TODAY)),
    ('jsshell', 'linux', 64, 'asan', (datetime.date(2013, 9, 1), TODAY)),
    ('jsshell', 'linux', 64, 'debug,asan', (datetime.date(2013, 9, 1), TODAY)),
    ('jsshell', 'linux', 32, None, (datetime.date(2012, 4, 18), TODAY)),
    ('jsshell', 'mac', 64, None, (datetime.date(2012, 4, 18), TODAY)),
    ('jsshell', 'win', 32, None, (datetime.date(2012, 4, 18), TODAY)),
    # anything else on win 64
    ('firefox', 'win', 64, None, (datetime.date(2010, 5, 28), TODAY)),
    # anything else
    ('firefox', 'linux', 64, None, (datetime.date(2009, 1, 1), TODAY)),
])
def test_get_default_date_range(app, os, bits, build_type, expected_range):
    fetch_config = create_config(app, os, bits)
    if build_type:
        fetch_config.set_build_type(build_type)

    assert expected_range == cli.get_default_date_range(fetch_config)
