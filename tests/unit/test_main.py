from __future__ import absolute_import, print_function

import tempfile
import unittest
from datetime import date

import pytest
import requests
from mock import ANY, MagicMock, Mock, call, patch

from mozregression import __version__, config, errors, main
from mozregression.bisector import Bisection, Bisector, IntegrationHandler, NightlyHandler
from mozregression.download_manager import BuildDownloadManager
from mozregression.telemetry import UsageMetrics
from mozregression.test_runner import CommandTestRunner, ManualTestRunner


class AppCreator(object):
    def __init__(self, logger):
        self.app = None
        self.logs = []
        logger.info = self.logs.append
        logger.warning = self.logs.append

    def __call__(self, argv):
        config = main.cli(argv, conf_file=None)
        config.validate()
        self.app = main.Application(config.fetch_config, config.options)
        return self.app

    def find_in_log(self, msg, exact=True):
        if exact:
            return msg in self.logs
        for m in self.logs:
            if msg in m:
                return True

    def clear(self):
        if self.app:
            self.app.clear()


@pytest.yield_fixture
def create_app(mocker):
    """allow to create an Application and ensure that clear() is called"""
    creator = AppCreator(mocker.patch("mozregression.main.LOG"))
    yield creator
    creator.clear()


def test_app_get_manual_test_runner(create_app):
    app = create_app(["--profile=/prof"])
    assert isinstance(app.test_runner, ManualTestRunner)
    assert app.test_runner.launcher_kwargs == dict(
        addons=[],
        profile="/prof",
        cmdargs=["--allow-downgrade"],
        preferences=[],
        adb_profile_dir=None,
    )


def test_app_get_command_test_runner(create_app):
    app = create_app(["--command=echo {binary}"])
    assert isinstance(app.test_runner, CommandTestRunner)
    assert app.test_runner.command == "echo {binary}"


@pytest.mark.parametrize(
    "argv,background_dl_policy,size_limit",
    [
        ([], "cancel", 0),
        # without persist, cancel policy is forced
        (["--background-dl-policy=keep"], "cancel", 0),
        (["--persist=1", "--background-dl-policy=keep"], "keep", 0),
        # persist limit
        (["--persist-size-limit=10"], "cancel", 10 * 1073741824),
    ],
)
def test_app_get_download_manager(create_app, argv, background_dl_policy, size_limit):
    app = create_app(argv)
    assert isinstance(app.build_download_manager, BuildDownloadManager)
    assert app.build_download_manager.background_dl_policy == background_dl_policy
    assert app.build_download_manager.persist_limit.size_limit == size_limit
    assert app.build_download_manager.persist_limit.file_limit == 5


def test_app_get_bisector(create_app):
    app = create_app([])
    assert isinstance(app.bisector, Bisector)


def test_app_bisect_nightlies_finished(create_app, mocker):
    app = create_app(["-g=2015-06-01", "-b=2015-06-02"])
    app.bisector.bisect = Mock(return_value=Bisection.FINISHED)
    app._bisect_integration = Mock(return_value=0)
    NightlyHandler = mocker.patch("mozregression.main.NightlyHandler")
    nh = Mock(bad_date=date.today(), good_revision="c1", bad_revision="c2")
    NightlyHandler.return_value = nh
    assert app.bisect_nightlies() == 0
    app.bisector.bisect.assert_called_once_with(ANY, date(2015, 6, 1), date(2015, 6, 2))
    assert create_app.find_in_log("Got as far as we can go bisecting nightlies...")
    app._bisect_integration.assert_called_once_with("c1", "c2", expand=config.DEFAULT_EXPAND)


def test_app_bisect_nightlies_no_data(create_app):
    app = create_app(["-g=2015-06-01", "-b=2015-06-02"])
    app.bisector.bisect = Mock(return_value=Bisection.NO_DATA)
    assert app.bisect_nightlies() == 1
    assert create_app.find_in_log("Unable to get valid builds within the given range.", False)


@pytest.mark.parametrize("same_chsets", [True, False])
def test_app_bisect_integration_finished(create_app, same_chsets):
    argv = ["--good=c1", "--bad=%s" % ("c1" if same_chsets else "c2")]
    app = create_app(argv)
    app.bisector.bisect = Mock(return_value=Bisection.FINISHED)
    assert app.bisect_integration() == 0
    assert create_app.find_in_log("No more integration revisions, bisection finished.")
    if same_chsets:
        assert create_app.find_in_log(
            "It seems that you used two changesets" " that are in the same push.", False
        )


@pytest.mark.parametrize(
    "argv,expected_log",
    [
        (["--app=firefox", "--bits=64"], "--app=firefox --bits=64"),
        (["--persist", "blah stuff"], "--persist 'blah stuff'"),
        (["--addon=a b c", "--addon=d"], "'--addon=a b c' --addon=d"),
        (["--find-fix", "--arg=a b"], "--find-fix '--arg=a b'"),
        (["--profile=pro file"], "'--profile=pro file'"),
        (["-g", "2015-11-01", "-b", "2015-11-03"], "--good=2015-11-01 --bad=2015-11-03"),
    ],
)
def test_app_bisect_nightlies_user_exit(create_app, argv, expected_log, mocker):
    Handler = mocker.patch("mozregression.main.NightlyHandler")
    Handler.return_value = Mock(
        build_range=[Mock(repo_name="mozilla-central")],
        good_date="2015-11-01",
        bad_date="2015-11-03",
        spec=NightlyHandler,
    )

    app = create_app(argv)
    app.bisector.bisect = Mock(return_value=Bisection.USER_EXIT)
    sys = mocker.patch("mozregression.main.sys")
    sys.argv = argv
    assert app.bisect_nightlies() == 0
    assert create_app.find_in_log("To resume, run:")
    assert create_app.find_in_log(expected_log, False)
    assert create_app.find_in_log("--repo=mozilla-central", False)


def test_app_bisect_integration_user_exit(create_app, mocker):
    Handler = mocker.patch("mozregression.main.IntegrationHandler")
    Handler.return_value = Mock(
        build_range=[Mock(repo_name="mozilla-central")],
        good_revision="c1",
        bad_revision="c2",
        spec=IntegrationHandler,
    )

    app = create_app(["--good=c1", "--bad=c2"])
    app.bisector.bisect = Mock(return_value=Bisection.USER_EXIT)
    assert app.bisect_integration() == 0
    assert create_app.find_in_log("To resume, run:")
    assert create_app.find_in_log("--repo=mozilla-central", False)


def test_app_bisect_integration_no_data(create_app):
    app = create_app(["--good=c1", "--bad=c2"])
    app.bisector.bisect = Mock(return_value=Bisection.NO_DATA)
    assert app.bisect_integration() == 1
    assert create_app.find_in_log("There are no build artifacts for these changesets", False)


def test_app_bisect_ctrl_c_exit(create_app, mocker):
    app = create_app([])
    app.bisector.bisect = Mock(side_effect=KeyboardInterrupt)
    at_exit = mocker.patch("atexit.register")
    handler = MagicMock(good_revision="c1", bad_revision="c2")
    Handler = mocker.patch("mozregression.main.NightlyHandler")
    Handler.return_value = handler
    with pytest.raises(KeyboardInterrupt):
        app.bisect_nightlies()
    print(handler)
    at_exit.assert_called_once_with(app._on_exit_print_resume_info, handler)
    # call the atexit handler
    mocker.stopall()
    app._on_exit_print_resume_info(handler)
    handler.print_range.assert_called_once_with()


class TestCheckMozregresionVersion(unittest.TestCase):
    @patch("mozregression.main.LOG")
    @patch("requests.get")
    def test_version_is_upto_date(self, get, log):
        response = Mock(json=lambda: {"info": {"version": __version__}})
        get.return_value = response
        main.check_mozregression_version()
        self.assertFalse(log.critical.called)

    @patch("requests.get")
    def test_Exception_error(self, get):
        get.side_effect = requests.RequestException
        # exception is handled inside main.check_mozregression_version
        main.check_mozregression_version()
        self.assertRaises(requests.RequestException, get)

    @patch("mozregression.main.LOG")
    @patch("requests.get")
    def test_warn_if_version_is_not_up_to_date(self, get, log):
        response = Mock(json=lambda: {"info": {"version": 0}})
        get.return_value = response
        main.check_mozregression_version()
        self.assertEqual(log.warning.call_count, 2)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.app = Mock()
        self.logger = Mock()

    @patch("mozregression.main.send_telemetry_ping_oop")
    @patch("mozregression.main.LOG")
    @patch("mozregression.main.check_mozregression_version")
    @patch("mozlog.structured.commandline.setup_logging")
    @patch("mozregression.main.set_http_session")
    @patch("mozregression.main.Application")
    def do_cli(
        self,
        argv,
        Application,
        set_http_session,
        setup_logging,
        check_mozregression_version,
        log,
        send_telemetry_ping_oop,
        telemetry_enabled=True,
    ):
        self.logger = log

        def create_app(fetch_config, options):
            self.app.fetch_config = fetch_config
            self.app.options = options
            return self.app

        Application.side_effect = create_app
        try:
            with tempfile.NamedTemporaryFile("wt", delete=False) as tf:
                tf.write("enable-telemetry = {}\n".format("yes" if telemetry_enabled else "no"))
                tf.flush()
                # Use `func_defaults` in Python2.x and `__defaults__` in Python3.x.
                with patch.object(main.cli, "__defaults__", (None, tf.name, None)):
                    main.main(argv)
        except SystemExit as exc:
            self.assertEqual(send_telemetry_ping_oop.call_count, 1)
            self.assertEqual(
                send_telemetry_ping_oop.call_args,
                call(
                    UsageMetrics(
                        "console",
                        "firefox",
                        self.app.fetch_config.build_type,
                        self.app.options.good,
                        self.app.options.bad,
                        self.app.options.launch,
                    ),
                    telemetry_enabled,
                ),
            )
            return exc.code
        else:
            self.fail("mozregression.main.cli did not call sys.exit")

    def pop_logs(self):
        logs = []
        for i in range(len(self.logger.mock_calls)):
            call = self.logger.mock_calls.pop(0)
            logs.append((call[0], call[1][0]))
        return logs

    def pop_exit_error_msg(self):
        for lvl, msg in reversed(self.pop_logs()):
            if lvl == "error":
                return msg

    def test_without_args(self):
        self.app.bisect_nightlies.return_value = 0
        exitcode = self.do_cli([])
        # bisect_nightlies has been called
        self.app.bisect_nightlies.assert_called_with()
        # we exited with the return value of bisect_nightlies
        self.assertEqual(exitcode, 0)

    def test_bisect_integration(self):
        self.app.bisect_integration.return_value = 0
        exitcode = self.do_cli(["--good=a1", "--bad=b5"])
        self.assertEqual(exitcode, 0)
        self.app.bisect_integration.assert_called_with()

    def test_disable_telemetry(self):
        self.app.bisect_integration.return_value = 0
        exitcode = self.do_cli(["--good=a1", "--bad=b5"], telemetry_enabled=False)
        self.assertEqual(exitcode, 0)

    def test_handle_keyboard_interrupt(self):
        # KeyboardInterrupt is handled with a nice error message.
        self.app.bisect_nightlies.side_effect = KeyboardInterrupt
        exitcode = self.do_cli([])
        self.assertIn("Interrupted", exitcode)

    def test_handle_mozregression_errors(self):
        # Any MozRegressionError subclass is handled with a nice error message
        self.app.bisect_nightlies.side_effect = errors.MozRegressionError("my error")
        exitcode = self.do_cli([])
        self.assertNotEqual(exitcode, 0)
        self.assertIn("my error", self.pop_exit_error_msg())

    def test_handle_other_errors(self):
        # other exceptions are just thrown as usual
        # so we have complete stacktrace
        self.app.bisect_nightlies.side_effect = NameError
        self.assertRaises(NameError, self.do_cli, [])
