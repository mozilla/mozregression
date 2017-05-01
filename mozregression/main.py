# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Entry point for the mozregression command line.
"""

import os
import sys
import requests
import atexit
import pipes
import tempfile
import mozfile
import colorama

from mozlog import get_proxy_logger
from requests.exceptions import RequestException, HTTPError

from mozregression import __version__
from mozregression.config import TC_CREDENTIALS_FNAME, DEFAULT_EXPAND
from mozregression.cli import cli
from mozregression.errors import MozRegressionError, GoodBadExpectationError
from mozregression.bisector import (Bisector, NightlyHandler, InboundHandler,
                                    Bisection)
from mozregression.launchers import REGISTRY as APP_REGISTRY
from mozregression.network import set_http_session
from mozregression.test_runner import ManualTestRunner, CommandTestRunner
from mozregression.download_manager import BuildDownloadManager
from mozregression.persist_limit import PersistLimit
from mozregression.fetch_build_info import (NightlyInfoFetcher,
                                            InboundInfoFetcher)
from mozregression.json_pushes import JsonPushes
from mozregression.bugzilla import find_bugids_in_push, bug_url
from mozregression.approx_persist import ApproxPersistChooser

LOG = get_proxy_logger("main")


class Application(object):
    def __init__(self, fetch_config, options):
        self.fetch_config = fetch_config
        self.options = options
        self._test_runner = None
        self._bisector = None
        self._build_download_manager = None
        self._download_dir = options.persist
        self._rm_download_dir = False
        if not options.persist:
            self._download_dir = tempfile.mkdtemp()
            self._rm_download_dir = True
        launcher_class = APP_REGISTRY.get(fetch_config.app_name)
        launcher_class.check_is_runnable()
        # init global profile if required
        self._global_profile = None
        if options.profile_persistence in ('clone-first', 'reuse'):
            self._global_profile = launcher_class.create_profile(
                profile=options.profile,
                addons=options.addons,
                preferences=options.preferences,
                clone=options.profile_persistence == 'clone-first'
            )

    def clear(self):
        if self._build_download_manager:
            # cancel all possible downloads
            self._build_download_manager.cancel()
        if self._rm_download_dir:
            if self._build_download_manager:
                # we need to wait explicitly for downloading threads completion
                # here because it may remove a file in the download dir - and
                # in that case we could end up with a race condition when
                # we will remove the download dir. See
                # https://bugzilla.mozilla.org/show_bug.cgi?id=1231745
                self._build_download_manager.wait(raise_if_error=False)
            mozfile.remove(self._download_dir)
        if self._global_profile \
           and self.options.profile_persistence == 'clone-first':
            self._global_profile.cleanup()

    @property
    def test_runner(self):
        if self._test_runner is None:
            if self.options.command is None:
                self._test_runner = ManualTestRunner(launcher_kwargs=dict(
                    addons=self.options.addons,
                    profile=self._global_profile or self.options.profile,
                    cmdargs=self.options.cmdargs,
                    preferences=self.options.preferences,
                ))
            else:
                self._test_runner = CommandTestRunner(self.options.command)
        return self._test_runner

    @property
    def bisector(self):
        if self._bisector is None:
            self._bisector = Bisector(
                self.fetch_config, self.test_runner,
                self.build_download_manager,
                dl_in_background=self.options.background_dl,
                approx_chooser=(None if self.options.approx_policy != 'auto'
                                else ApproxPersistChooser(7)),
            )
        return self._bisector

    @property
    def build_download_manager(self):
        if self._build_download_manager is None:
            background_dl_policy = self.options.background_dl_policy
            if not self.options.persist:
                # cancel background downloads forced
                background_dl_policy = "cancel"
            self._build_download_manager = BuildDownloadManager(
                self._download_dir,
                background_dl_policy=background_dl_policy,
                persist_limit=PersistLimit(self.options.persist_size_limit)
            )
        return self._build_download_manager

    def bisect_nightlies(self):
        good_date, bad_date = self.options.good, self.options.bad
        handler = NightlyHandler(
            find_fix=self.options.find_fix,
            ensure_good_and_bad=self.options.mode != 'no-first-check',
        )
        result = self._do_bisect(handler, good_date, bad_date)
        if result == Bisection.FINISHED:
            LOG.info("Got as far as we can go bisecting nightlies...")
            handler.print_range()
            if self.fetch_config.can_go_inbound():
                LOG.info("Switching bisection method to taskcluster")
                self.fetch_config.set_repo(
                    self.fetch_config.get_nightly_repo(handler.bad_date))
                return self._bisect_inbounds(handler.good_revision,
                                             handler.bad_revision,
                                             expand=DEFAULT_EXPAND)
        elif result == Bisection.USER_EXIT:
            self._print_resume_info(handler)
        else:
            # NO_DATA
            LOG.info("Unable to get valid builds within the given"
                     " range. You should try to launch mozregression"
                     " again with a larger date range.")
            return 1
        return 0

    def bisect_inbounds(self):
        return self._bisect_inbounds(
            self.options.good,
            self.options.bad,
            ensure_good_and_bad=self.options.mode != 'no-first-check',
        )

    def _bisect_inbounds(self, good_rev, bad_rev, ensure_good_and_bad=False,
                         expand=0):
        LOG.info("Getting %s builds between %s and %s"
                 % (self.fetch_config.inbound_branch, good_rev, bad_rev))
        handler = InboundHandler(find_fix=self.options.find_fix,
                                 ensure_good_and_bad=ensure_good_and_bad)
        result = self._do_bisect(handler, good_rev, bad_rev, expand=expand)
        if result == Bisection.FINISHED:
            LOG.info("No more inbound revisions, bisection finished.")
            handler.print_range()
            if handler.good_revision == handler.bad_revision:
                LOG.warning(
                    "It seems that you used two changesets that are in"
                    " in the same push. Check the pushlog url."
                )
            elif len(handler.build_range) == 2:
                # range reduced to 2 pushes (at least ones with builds):
                # one good, one bad.
                result = handler.handle_merge()
                if result:
                    branch, good_rev, bad_rev = result
                    self.fetch_config.set_repo(branch)
                    return self._bisect_inbounds(good_rev, bad_rev,
                                                 expand=DEFAULT_EXPAND)
                else:
                    # print a bug if:
                    # (1) there really is only one bad push (and we're not
                    # just missing the builds for some intermediate builds)
                    # (2) there is only one bug number in that push
                    jp = JsonPushes(handler.build_range[1].repo_name)
                    num_pushes = len(jp.pushes_within_changes(
                        handler.build_range[0].changeset,
                        handler.build_range[1].changeset))
                    if num_pushes == 2:
                        bugids = find_bugids_in_push(
                            handler.build_range[1].repo_name,
                            handler.build_range[1].changeset
                        )
                        if len(bugids) == 1:
                            word = 'fix' if handler.find_fix else 'regression'
                            LOG.info("Looks like the following bug has the "
                                     " changes which introduced the"
                                     " {}:\n{}".format(word,
                                                       bug_url(bugids[0])))
        elif result == Bisection.USER_EXIT:
            self._print_resume_info(handler)
        else:
            # NO_DATA. With inbounds, this can not happen if changesets
            # are incorrect - so builds are probably too old
            LOG.info(
                'There are no build artifacts on inbound for these'
                ' changesets (they are probably too old).')
            return 1
        return 0

    def _do_bisect(self, handler, good, bad, **kwargs):
        try:
            return self.bisector.bisect(handler, good, bad, **kwargs)
        except (KeyboardInterrupt, MozRegressionError,
                RequestException) as exc:
            if handler.good_revision is not None and \
                    handler.bad_revision is not None and \
                    not isinstance(exc, GoodBadExpectationError):
                atexit.register(self._on_exit_print_resume_info, handler)
            raise

    def _print_resume_info(self, handler):
        # copy sys.argv, remove every --good/--bad/--repo related argument,
        # then add our own
        argv = sys.argv[:]
        args = ('--good', '--bad', '-g', '-b', '--good-rev', '--bad-rev',
                '--repo')
        indexes_to_remove = []
        for i, arg in enumerate(argv):
            if i in indexes_to_remove:
                continue
            for karg in args:
                if karg == arg:
                    # handle '--good 2015-01-01'
                    indexes_to_remove.extend((i, i + 1))
                    break
                elif arg.startswith(karg + '='):
                    # handle '--good=2015-01-01'
                    indexes_to_remove.append(i)
                    break
        for i in reversed(indexes_to_remove):
            del argv[i]

        argv.append('--repo=%s' % handler.build_range[0].repo_name)

        if hasattr(handler, 'good_date'):
            argv.append('--good=%s' % handler.good_date)
            argv.append('--bad=%s' % handler.bad_date)
        else:
            argv.append('--good=%s' % handler.good_revision)
            argv.append('--bad=%s' % handler.bad_revision)

        LOG.info('To resume, run:')
        LOG.info(' '.join([pipes.quote(arg) for arg in argv]))

    def _on_exit_print_resume_info(self, handler):
        handler.print_range()
        self._print_resume_info(handler)

    def _launch(self, fetcher_class):
        fetcher = fetcher_class(self.fetch_config)
        build_info = fetcher.find_build_info(self.options.launch)
        self.build_download_manager.focus_download(build_info)
        self.test_runner.run_once(build_info)

    def launch_nightlies(self):
        self._launch(NightlyInfoFetcher)

    def launch_inbound(self):
        self._launch(InboundInfoFetcher)


def pypi_latest_version():
    url = "https://pypi.python.org/pypi/mozregression/json"
    return requests.get(url, timeout=10).json()['info']['version']


def check_mozregression_version():
    try:
        mozregression_version = pypi_latest_version()
    except (RequestException, KeyError, ValueError):
        LOG.critical("Unable to get latest version from pypi.")
        return

    if __version__ != mozregression_version:
        LOG.warning("You are using mozregression version %s, "
                    "however version %s is available."
                    % (__version__, mozregression_version))

        LOG.warning("You should consider upgrading via the 'pip install"
                    " --upgrade mozregression' command.")


def main(argv=None, namespace=None, check_new_version=True):
    """
    main entry point of mozregression command line.
    """
    # terminal color support on windows
    if os.name == 'nt':
        colorama.init()

    if sys.version_info <= (2, 7, 9):
        # requests uses urllib3, and on python <= 2.7.9 there will be a lot
        # of warnings that we do not want. See
        # https://bugzilla.mozilla.org/show_bug.cgi?id=1199020
        import logging
        logging.captureWarnings(True)

    config, app = None, None
    try:
        config = cli(argv=argv, namespace=namespace)
        if check_new_version:
            check_mozregression_version()
        config.validate()
        set_http_session(get_defaults={"timeout": config.options.http_timeout})
        app = Application(config.fetch_config, config.options)

        method = getattr(app, config.action)
        sys.exit(method())

    except KeyboardInterrupt:
        sys.exit("\nInterrupted.")
    except (MozRegressionError, RequestException) as exc:
        if isinstance(exc, HTTPError) and exc.response.status_code == 401:
            # remove the taskcluster credential file - looks like it's wrong
            # anyway. This will force mozregression to ask again next time.
            mozfile.remove(TC_CREDENTIALS_FNAME)
        LOG.error(str(exc)) if config else sys.exit(str(exc))
        sys.exit(1)
    finally:
        if app:
            app.clear()


if __name__ == "__main__":
    main()
