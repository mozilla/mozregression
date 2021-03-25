from __future__ import absolute_import

import datetime
import os
import tempfile
import unittest

import pytest
from mock import patch
from mozlog import get_default_logger

from mozregression import cli, errors
from mozregression.releases import releases


class TestParseDate(unittest.TestCase):
    def test_valid_date(self):
        date = cli.parse_date("2014-07-05")
        self.assertEqual(date, datetime.date(2014, 7, 5))

    def test_parse_buildid(self):
        date = cli.parse_date("20151103030248")
        self.assertEqual(date, datetime.datetime(2015, 11, 3, 3, 2, 48))

    def test_invalid_date(self):
        self.assertRaises(errors.DateFormatError, cli.parse_date, "invalid_format")
        # test invalid buildid (43 is not a valid day)
        self.assertRaises(errors.DateFormatError, cli.parse_date, "20151143030248")
        self.assertRaises(errors.DateValueError, cli.parse_date, "2020-11-0")
        self.assertRaises(errors.DateValueError, cli.parse_date, "2020-13-01")


class TestParseBits(unittest.TestCase):
    @patch("mozregression.cli.mozinfo")
    def test_parse_32(self, mozinfo):
        mozinfo.bits = 32
        self.assertEqual(cli.parse_bits("32"), 32)
        self.assertEqual(cli.parse_bits("64"), 32)

    @patch("mozregression.cli.mozinfo")
    def test_parse_64(self, mozinfo):
        mozinfo.bits = 64
        self.assertEqual(cli.parse_bits("32"), 32)
        self.assertEqual(cli.parse_bits("64"), 64)


class TestPreferences(unittest.TestCase):
    def test_preferences_file(self):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, "w") as conf_file:
            conf_file.write('{ "browser.tabs.remote.autostart": false }')

        prefs_files = [filepath]
        prefs = cli.preferences(prefs_files, None, None)
        self.assertEqual(prefs, [("browser.tabs.remote.autostart", False)])

    def test_preferences_args(self):
        prefs_args = ["browser.tabs.remote.autostart:false"]

        prefs = cli.preferences(None, prefs_args, None)
        self.assertEqual(prefs, [("browser.tabs.remote.autostart", False)])

        prefs_args = ["browser.tabs.remote.autostart"]

        prefs = cli.preferences(None, prefs_args, None)
        self.assertEqual(len(prefs), 0)


class TestCli(unittest.TestCase):
    def _create_conf_file(self, content):
        handle, filepath = tempfile.mkstemp()
        self.addCleanup(os.unlink, filepath)

        with os.fdopen(handle, "w") as conf_file:
            conf_file.write(content)
        return filepath

    def test_get_erronous_cfg_defaults(self):
        filepath = self._create_conf_file("aaaaaaaaaaa [Defaults]\n")

        with self.assertRaises(errors.MozRegressionError):
            cli.cli(conf_file=filepath)

    def test_get_defaults(self):
        valid_values = {
            "http-timeout": "10.2",
            "persist": "/home/foo/.mozregression",
            "bits": "64",
        }

        content = ["%s=%s\n" % (key, value) for key, value in valid_values.items()]
        filepath = self._create_conf_file("\n".join(content))

        options = cli.cli(["--bits=32"], conf_file=filepath).options

        self.assertEqual(options.http_timeout, 10.2)
        self.assertEqual(options.persist, "/home/foo/.mozregression")
        self.assertEqual(options.bits, "32")

    def test_warn_invalid_build_type_in_conf(self):
        filepath = self._create_conf_file("build-type=foo\n")
        conf = cli.cli([], conf_file=filepath)
        warns = []
        conf.logger.warning = warns.append
        conf.validate()
        self.assertIn(
            "Unable to find a suitable build type 'foo'." " (Defaulting to 'shippable')",
            warns,
        )


def do_cli(*argv, conf_file=None):
    conf = cli.cli(argv, conf_file=conf_file)
    conf.validate()
    return conf


def test_get_usage():
    output = []
    with patch("sys.stdout") as stdout:
        stdout.write.side_effect = output.append

        with pytest.raises(SystemExit) as exc:
            do_cli("-h")
    assert exc.value.code == 0
    assert "usage:" in "".join(output)


def test_list_build_types(mocker):
    output = []
    with patch("sys.stdout") as stdout:
        stdout.write.side_effect = output.append

        with pytest.raises(SystemExit) as exc:
            do_cli("--list-build-types")
    assert exc.value.code == 0
    assert "firefox:\n  shippable" in "".join(output)


def test_no_args():
    config = do_cli()
    # application is by default firefox
    assert config.fetch_config.app_name == "firefox"
    # nightly by default
    assert config.action == "bisect_nightlies"
    assert config.options.good == datetime.date.today() - datetime.timedelta(days=365)
    assert config.options.bad == datetime.date.today()
    # telemetry is by default enabled
    assert config.enable_telemetry


TODAY = datetime.date.today()
SOME_DATE = TODAY + datetime.timedelta(days=-20)
SOME_OLDER_DATE = TODAY + datetime.timedelta(days=-10)


@pytest.mark.parametrize(
    "params,good,bad",
    [
        # we can use dates with integration branches
        (
            ["--good=%s" % SOME_DATE, "--bad=%s" % SOME_OLDER_DATE, "--repo=m-i"],
            SOME_DATE,
            SOME_OLDER_DATE,
        ),
        # non opt build flavors are also found using taskcluster
        (
            ["--good=%s" % SOME_DATE, "--bad=%s" % SOME_OLDER_DATE, "-B", "debug"],
            SOME_DATE,
            SOME_OLDER_DATE,
        ),
    ],
)
def test_use_taskcluster_bisection_method(params, good, bad):
    config = do_cli(*params)

    assert config.action == "bisect_integration"  # meaning taskcluster usage
    # compare dates using the representation, as we may have
    # date / datetime instances
    assert config.options.good.strftime("%Y-%m-%d") == good.strftime("%Y-%m-%d")
    assert config.options.bad.strftime("%Y-%m-%d") == bad.strftime("%Y-%m-%d")


def test_find_fix_reverse_default_dates():
    config = do_cli("--find-fix")
    # application is by default firefox
    assert config.fetch_config.app_name == "firefox"
    # nightly by default
    assert config.action == "bisect_nightlies"
    assert config.options.bad == datetime.date.today() - datetime.timedelta(days=365)
    assert config.options.good == datetime.date.today()


def test_with_releases():
    releases_data = sorted(((k, v) for k, v in releases().items()), key=(lambda k_v: k_v[0]))
    conf = do_cli(
        "--bad=%s" % releases_data[-1][0],
        "--good=%s" % releases_data[0][0],
    )
    assert str(conf.options.good) == releases_data[0][1]
    assert str(conf.options.bad) == releases_data[-1][1]


@pytest.mark.parametrize(
    "args,action,value",
    [
        (["--launch=34"], "launch_nightlies", cli.parse_date(releases()[34])),
        (["--launch=2015-11-01"], "launch_nightlies", datetime.date(2015, 11, 1)),
        (["--launch=abc123"], "launch_integration", "abc123"),
        (
            ["--launch=2015-11-01", "--repo=m-i"],
            "launch_integration",
            datetime.date(2015, 11, 1),
        ),
    ],
)
def test_launch(args, action, value):
    config = do_cli(*args)
    assert config.action == action
    assert config.options.launch == value


@pytest.mark.parametrize(
    "args,repo,value",
    [
        (["--launch=60.0", "--repo=m-r"], "mozilla-release", "FIREFOX_60_0_RELEASE"),
        (["--launch=61", "--repo=m-r"], "mozilla-release", "FIREFOX_61_0_RELEASE"),
        (["--launch=62.0.1"], "mozilla-release", "FIREFOX_62_0_1_RELEASE"),
        (["--launch=63.0b4", "--repo=m-b"], "mozilla-beta", "FIREFOX_63_0b4_RELEASE"),
        (["--launch=64", "--repo=m-b"], "mozilla-beta", "FIREFOX_RELEASE_64_BASE"),
        (["--launch=65.0b11"], "mozilla-beta", "FIREFOX_65_0b11_RELEASE"),
    ],
)
def test_versions(args, repo, value):
    config = do_cli(*args)
    assert config.fetch_config.repo == repo
    assert config.options.launch == value


def test_bad_date_later_than_good():
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli("--good=2015-01-01", "--bad=2015-01-10", "--find-fix")
    assert "is later than good" in str(exc.value)
    assert "You should not use the --find-fix" in str(exc.value)


def test_good_date_later_than_bad():
    with pytest.raises(errors.MozRegressionError) as exc:
        do_cli("--good=2015-01-10", "--bad=2015-01-01")
    assert "is later than bad" in str(exc.value)
    assert "you wanted to use the --find-fix" in str(exc.value)


def test_basic_integration():
    config = do_cli("--good=c1", "--bad=c5")
    assert config.fetch_config.app_name == "firefox"
    assert config.action == "bisect_integration"
    assert config.options.good == "c1"
    assert config.options.bad == "c5"


def test_list_releases(mocker):
    out = []
    stdout = mocker.patch("sys.stdout")
    stdout.write = out.append
    with pytest.raises(SystemExit):
        do_cli("--list-releases")
    assert "Valid releases:" in "\n".join(out)


def test_write_confif(mocker):
    out = []
    stdout = mocker.patch("sys.stdout")
    stdout.write = out.append
    write_config = mocker.patch("mozregression.cli.write_config")
    with pytest.raises(SystemExit):
        do_cli("--write-conf")
    assert len(write_config.mock_calls) == 1


def test_warning_no_conf(mocker):
    out = []
    stdout = mocker.patch("sys.stdout")
    stdout.write = out.append
    cli.cli([], conf_file="blah_this is not a valid file_I_hope")
    assert "You should use a config file" in "\n".join(out)


@pytest.mark.parametrize(
    "args,enabled",
    [
        ([], False),  # not enabled by default, because build_type is opt
        (["-P=stdout"], True),  # explicitly enabled
        (["-B=debug"], True),  # enabled because build type is not opt
        (["-B=debug", "-P=none"], False),  # explicitly disabled
    ],
)
def test_process_output_enabled(args, enabled):
    do_cli(*args)
    log_filter = get_default_logger("process").component_filter

    result = log_filter({"some": "data"})
    if enabled:
        assert result
    else:
        assert not result


@pytest.mark.parametrize(
    "mozversion_msg,shown",
    [
        ("platform_changeset: abc123", False),
        ("application_changeset: abc123", True),
        ("application_version: stuff:thing", True),
        ("application_remotingname: stuff", False),
        ("application_id: stuff", False),
        ("application_vendor: stuff", False),
        ("application_display_name: stuff", False),
        ("not a valid key value pair", True),
    ],
)
def test_mozversion_output_filtered(mozversion_msg, shown):
    do_cli()
    log_filter = get_default_logger("mozversion").component_filter
    log_data = {"message": mozversion_msg}

    result = log_filter(log_data)
    if shown:
        assert result == log_data
    else:
        assert not result


@pytest.mark.parametrize("enable_telemetry", (True, False))
def test_telemetry(enable_telemetry):
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("enable-telemetry = %s\n" % ("yes" if enable_telemetry else "no"))
        f.close()
        config = do_cli(conf_file=f.name)
        assert config.enable_telemetry is enable_telemetry
        os.unlink(f.name)
