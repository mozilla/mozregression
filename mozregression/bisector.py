from __future__ import absolute_import

import math
import os
import threading
from abc import ABCMeta, abstractmethod

from mozlog import get_proxy_logger

from mozregression.branches import find_branch_in_merge_commit, get_name
from mozregression.build_range import get_integration_range, get_nightly_range
from mozregression.dates import to_datetime
from mozregression.errors import (
    EmptyPushlogError,
    GoodBadExpectationError,
    LauncherError,
    MozRegressionError,
)
from mozregression.history import BisectionHistory
from mozregression.json_pushes import JsonPushes

LOG = get_proxy_logger("Bisector")


def compute_steps_left(steps):
    if steps <= 1:
        return 0
    return math.trunc(math.log(steps, 2))


class BisectorHandler(metaclass=ABCMeta):
    """
    React to events of a :class:`Bisector`. This is intended to be subclassed.

    A BisectorHandler keep the state of the current bisection process.
    """

    def __init__(self, find_fix=False, ensure_good_and_bad=False):
        self.find_fix = find_fix
        self.ensure_good_and_bad = ensure_good_and_bad
        self.found_repo = None
        self.build_range = None
        self.good_revision = None
        self.bad_revision = None

    def set_build_range(self, build_range):
        """
        Save a reference of the :class:`mozregression.build_range.BuildData`
        instance.

        This is called by the bisector before each step of the bisection
        process.
        """
        self.build_range = build_range

    @abstractmethod
    def _print_progress(self, new_data):
        """
        Log the current state of the bisection process.
        """
        raise NotImplementedError

    def _reverse_if_find_fix(self, var1, var2):
        return (var1, var2) if not self.find_fix else (var2, var1)

    def initialize(self):
        """
        Initialize some data at the beginning of each step of a bisection
        process.

        This will only be called if there is some build data.
        """
        # these values could be missing for old integration builds
        # until we tried the builds
        repo = self.build_range[-1].repo_url
        if repo is not None:
            # do not update repo if we can' find it now
            # else we may override a previously defined one
            self.found_repo = repo
        self.good_revision, self.bad_revision = self._reverse_if_find_fix(
            self.build_range[0].changeset, self.build_range[-1].changeset
        )

    def get_pushlog_url(self):
        first_rev, last_rev = self.get_range()
        if first_rev == last_rev:
            return "%s/pushloghtml?changeset=%s" % (self.found_repo, first_rev)
        return "%s/pushloghtml?fromchange=%s&tochange=%s" % (self.found_repo, first_rev, last_rev,)

    def get_range(self):
        return self._reverse_if_find_fix(self.good_revision, self.bad_revision)

    def print_range(self, good_date=None, bad_date=None, full=True):
        """
        Log the state of the current state of the bisection process, with an
        appropriate pushlog url.
        """
        if full:
            if good_date and bad_date:
                good_date = " (%s)" % good_date
                bad_date = " (%s)" % bad_date
            words = self._reverse_if_find_fix("Last", "First")
            LOG.info(
                "%s good revision: %s%s"
                % (words[0], self.good_revision, good_date if good_date else "")
            )
            LOG.info(
                "%s bad revision: %s%s"
                % (words[1], self.bad_revision, bad_date if bad_date else "")
            )
        LOG.info("Pushlog:\n%s\n" % self.get_pushlog_url())

    def build_good(self, mid, new_data):
        """
        Called by the Bisector when a build is good.

        *new_data* is ensured to contain at least two elements.
        """
        self._print_progress(new_data)

    def build_bad(self, mid, new_data):
        """
        Called by the Bisector when a build is bad.

        *new_data* is ensured to contain at least two elements.
        """
        self._print_progress(new_data)

    def build_retry(self, mid):
        pass

    def build_skip(self, mid):
        pass

    def no_data(self):
        pass

    def finished(self):
        pass

    def user_exit(self, mid):
        pass


class NightlyHandler(BisectorHandler):
    create_range = staticmethod(get_nightly_range)
    good_date = None
    bad_date = None

    def initialize(self):
        BisectorHandler.initialize(self)
        # register dates
        self.good_date, self.bad_date = self._reverse_if_find_fix(
            self.build_range[0].build_date, self.build_range[-1].build_date
        )

    def _print_progress(self, new_data):
        next_good_date = new_data[0].build_date
        next_bad_date = new_data[-1].build_date
        next_days_range = abs((to_datetime(next_bad_date) - to_datetime(next_good_date)).days)
        LOG.info(
            "Narrowed nightly regression window from"
            " [%s, %s] (%d days) to [%s, %s] (%d days)"
            " (~%d steps left)"
            % (
                self.good_date,
                self.bad_date,
                abs((to_datetime(self.bad_date) - to_datetime(self.good_date)).days),
                next_good_date,
                next_bad_date,
                next_days_range,
                compute_steps_left(next_days_range),
            )
        )

    def _print_date_range(self):
        words = self._reverse_if_find_fix("Newest", "Oldest")
        LOG.info("%s known good nightly: %s" % (words[0], self.good_date))
        LOG.info("%s known bad nightly: %s" % (words[1], self.bad_date))

    def user_exit(self, mid):
        self._print_date_range()

    def are_revisions_available(self):
        return self.good_revision is not None and self.bad_revision is not None

    def get_date_range(self):
        return self._reverse_if_find_fix(self.good_date, self.bad_date)

    def print_range(self, full=True):
        if self.found_repo is None:
            # this may happen if we are bisecting old builds without
            # enough tests of the builds.
            LOG.error(
                "Sorry, but mozregression was unable to get"
                " a repository - no pushlog url available."
            )
            # still we can print date range
            if full:
                self._print_date_range()
        elif self.are_revisions_available():
            BisectorHandler.print_range(self, self.good_date, self.bad_date, full=full)
        else:
            if full:
                self._print_date_range()
            LOG.info("Pushlog:\n%s\n" % self.get_pushlog_url())

    def get_pushlog_url(self):
        assert self.found_repo
        if self.are_revisions_available():
            return BisectorHandler.get_pushlog_url(self)
        else:
            start, end = self.get_date_range()
            return "%s/pushloghtml?startdate=%s&enddate=%s\n" % (self.found_repo, start, end,)


class IntegrationHandler(BisectorHandler):
    create_range = staticmethod(get_integration_range)

    def _print_progress(self, new_data):
        LOG.info(
            "Narrowed integration regression window from [%s, %s]"
            " (%d builds) to [%s, %s] (%d builds)"
            " (~%d steps left)"
            % (
                self.build_range[0].short_changeset,
                self.build_range[-1].short_changeset,
                len(self.build_range),
                new_data[0].short_changeset,
                new_data[-1].short_changeset,
                len(new_data),
                compute_steps_left(len(new_data)),
            )
        )

    def user_exit(self, mid):
        words = self._reverse_if_find_fix("Newest", "Oldest")
        LOG.info("%s known good integration revision: %s" % (words[0], self.good_revision))
        LOG.info("%s known bad integration revision: %s" % (words[1], self.bad_revision))

    def _choose_integration_branch(self, changeset):
        """
        Tries to determine which integration branch the given changeset
        originated from by checking the date the changeset first showed up
        in each repo. The repo with the earliest date is chosen.
        """
        landings = {}
        for k in ("autoland", "mozilla-inbound"):
            jp = JsonPushes(k)

            try:
                push = jp.push(changeset, full="1")
                landings[k] = push.timestamp
            except EmptyPushlogError:
                LOG.debug("Didn't find %s in %s" % (changeset, k))

        repo = min(landings, key=landings.get)
        LOG.debug("Repo '%s' seems to have the earliest push" % repo)
        return repo

    def handle_merge(self):
        # let's check if we are facing a merge, and in that case,
        # continue the bisection from the merged branch.
        result = None

        LOG.debug("Starting merge handling...")
        # we have to check the commit of the most recent push
        most_recent_push = self.build_range[1]
        jp = JsonPushes(most_recent_push.repo_name)
        push = jp.push(most_recent_push.changeset, full="1")
        msg = push.changeset["desc"]
        LOG.debug("Found commit message:\n%s\n" % msg)
        branch = find_branch_in_merge_commit(msg, most_recent_push.repo_name)
        if not (branch and len(push.changesets) >= 2):
            # We did not find a branch, lets check the integration branches if we are bisecting m-c
            LOG.debug("Did not find a branch, checking all integration branches")
            if (
                get_name(most_recent_push.repo_name) == "mozilla-central"
                and len(push.changesets) >= 2
            ):
                branch = self._choose_integration_branch(most_recent_push.changeset)
                oldest = push.changesets[0]["node"]
                youngest = push.changesets[-1]["node"]
                LOG.info(
                    "************* Switching to %s by"
                    " process of elimination (no branch detected in"
                    " commit message)" % branch
                )
            else:
                return
        else:
            # so, this is a merge. see how many changesets are in it, if it
            # is just one, we have our answer
            if len(push.changesets) == 2:
                LOG.info(
                    "Merge commit has only two revisions (one of which "
                    "is the merge): we are done"
                )
                return

            # Otherwise, we can find the oldest and youngest
            # changesets, and the branch where the merge comes from.
            oldest = push.changesets[0]["node"]
            # exclude the merge commit
            youngest = push.changesets[-2]["node"]
            LOG.info("************* Switching to %s" % branch)

        # we can't use directly the oldest changeset because we
        # don't know yet if it is good.
        #
        # PUSH1    PUSH2
        # [1 2] [3 4 5 6 7]
        #    G    MERGE  B
        #
        # so first grab the previous push to get the last known good
        # changeset. This needs to be done on the right branch.
        try:
            jp2 = JsonPushes(branch)
            raw = [int(p.push_id) for p in jp2.pushes_within_changes(oldest, youngest)]
            data = jp2.pushes(startID=str(min(raw) - 2), endID=str(max(raw)),)

            older = data[0].changeset
            youngest = data[-1].changeset

            # we are ready to bisect further
            gr, br = self._reverse_if_find_fix(older, youngest)
            result = (branch, gr, br)
        except MozRegressionError:
            LOG.debug("Got exception", exc_info=True)
            raise MozRegressionError(
                "Unable to exploit the merge commit. Origin branch is {}, and"
                " the commit message for {} was:\n{}".format(
                    most_recent_push.repo_name, most_recent_push.short_changeset, msg
                )
            )
        LOG.debug("End merge handling")
        return result


class IndexPromise(object):
    """
    A promise to get a build index.

    Provide a callable object that gives the next index when called.
    """

    def __init__(self, index, callback=None, args=()):
        self.thread = None
        self.index = index
        if callback:
            self.thread = threading.Thread(target=self._run, args=(callback,) + args)
            self.thread.start()

    def _run(self, callback, *args):
        self.index = callback(self.index, *args)

    def __call__(self):
        if self.thread:
            self.thread.join()
        return self.index


class Bisection(object):
    RUNNING = 0
    NO_DATA = 1
    FINISHED = 2
    USER_EXIT = 3

    def __init__(
        self,
        handler,
        build_range,
        download_manager,
        test_runner,
        dl_in_background=True,
        approx_chooser=None,
    ):
        self.handler = handler
        self.build_range = build_range
        self.download_manager = download_manager
        self.test_runner = test_runner
        self.dl_in_background = dl_in_background
        self.history = BisectionHistory()
        self.approx_chooser = approx_chooser

    def search_mid_point(self, interrupt=None):
        self.handler.set_build_range(self.build_range)
        return self._search_mid_point(interrupt=interrupt)

    def _search_mid_point(self, interrupt=None):
        return self.build_range.mid_point(interrupt=interrupt)

    def init_handler(self, mid_point):
        if len(self.build_range) == 0:
            self.handler.no_data()
            return self.NO_DATA

        self.handler.initialize()

        if mid_point == 0:
            self.handler.finished()
            return self.FINISHED
        return self.RUNNING

    def download_build(self, mid_point, allow_bg_download=True):
        """
        Download the build for the given mid_point.

        This call may start the download of next builds in background (if
        dl_in_background evaluates to True). Note that the mid point may
        change in this case.

        Returns a couple (index_promise, build_infos) where build_infos
        is the dict of build infos for the build.
        """
        build_infos = self.handler.build_range[mid_point]
        return self._download_build(mid_point, build_infos, allow_bg_download=allow_bg_download)

    def _find_approx_build(self, mid_point, build_infos):
        approx_index, persist_files = None, ()
        if self.approx_chooser:
            # try to find an approx build
            persist_files = os.listdir(self.download_manager.destdir)
            # first test if we have the exact file - if we do,
            # just act as usual, the downloader will take care of it.
            if build_infos.persist_filename not in persist_files:
                approx_index = self.approx_chooser.index(
                    self.build_range, build_infos, persist_files
                )
        if approx_index is not None:
            # we found an approx build. First, stop possible background
            # downloads, then update the mid point and build info.
            if self.download_manager.background_dl_policy == "cancel":
                self.download_manager.cancel()

            old_url = build_infos.build_url
            mid_point = approx_index
            build_infos = self.build_range[approx_index]
            fname = self.download_manager.get_dest(build_infos.persist_filename)
            LOG.info(
                "Using `%s` as an acceptable approximated"
                " build file instead of downloading %s" % (fname, old_url)
            )
            build_infos.build_file = fname
        return (approx_index is not None, mid_point, build_infos, persist_files)

    def _download_build(self, mid_point, build_infos, allow_bg_download=True):
        found, mid_point, build_infos, persist_files = self._find_approx_build(
            mid_point, build_infos
        )
        if not found and self.download_manager:
            # else, do the download. Note that nothing will
            # be downloaded if the exact build file is already present.
            self.download_manager.focus_download(build_infos)
        callback = None
        if self.dl_in_background and allow_bg_download:
            callback = self._download_next_builds
        return (IndexPromise(mid_point, callback, args=(persist_files,)), build_infos)

    def _download_next_builds(self, mid_point, persist_files=()):
        # start downloading the next builds.
        # note that we don't have to worry if builds are already
        # downloaded, or if our build infos are the same because
        # this will be handled by the downloadmanager.
        def start_dl(r):
            # first get the next mid point
            # this will trigger some blocking downloads
            # (we need to find the build info)
            m = r.mid_point()
            if len(r) != 0:
                # non-blocking download of the build
                if (
                    self.approx_chooser
                    and self.approx_chooser.index(r, r[m], persist_files) is not None
                ):
                    pass  # nothing to download, we have an approx build
                else:
                    self.download_manager.download_in_background(r[m])

        bdata = self.build_range[mid_point]
        # download next left mid point
        start_dl(self.build_range[mid_point:])
        # download right next mid point
        start_dl(self.build_range[: mid_point + 1])
        # since we called mid_point() on copy of self.build_range instance,
        # the underlying cache may have changed and we need to find the new
        # mid point.
        self.build_range.filter_invalid_builds()
        return self.build_range.index(bdata)

    def evaluate(self, build_infos):
        verdict = self.test_runner.evaluate(build_infos, allow_back=bool(self.history))
        # old builds do not have metadata about the repo. But once
        # the build is installed, we may have it
        if self.handler.found_repo is None:
            self.handler.found_repo = build_infos.repo_url
        return verdict

    def ensure_good_and_bad(self):
        good, bad = self.build_range[0], self.build_range[-1]
        if self.handler.find_fix:
            good, bad = bad, good

        LOG.info("Testing good and bad builds to ensure that they are" " really good and bad...")
        self.download_manager.focus_download(good)
        if self.dl_in_background:
            self.download_manager.download_in_background(bad)

        def _evaluate(build_info, expected):
            while 1:
                res = self.test_runner.evaluate(build_info)
                if res == expected[0]:
                    return True
                elif res == "s":
                    LOG.info("You can not skip this build.")
                elif res == "e":
                    return
                elif res == "r":
                    pass
                else:
                    raise GoodBadExpectationError(
                        "Build was expected to be %s! The initial good/bad"
                        " range seems incorrect." % expected
                    )

        if _evaluate(good, "good"):
            self.download_manager.focus_download(bad)
            if self.dl_in_background:
                # download next build (mid) in background
                self.download_manager.download_in_background(
                    self.build_range[self.build_range.mid_point()]
                )
            return _evaluate(bad, "bad")

    def handle_verdict(self, mid_point, verdict):
        if verdict == "g":
            # if build is good and we are looking for a regression, we
            # have to split from
            # [G, ?, ?, G, ?, B]
            # to
            #          [G, ?, B]
            self.history.add(self.build_range, mid_point, verdict)
            if not self.handler.find_fix:
                self.build_range = self.build_range[mid_point:]
            else:
                self.build_range = self.build_range[: mid_point + 1]
            self.handler.build_good(mid_point, self.build_range)
        elif verdict == "b":
            # if build is bad and we are looking for a regression, we
            # have to split from
            # [G, ?, ?, B, ?, B]
            # to
            # [G, ?, ?, B]
            self.history.add(self.build_range, mid_point, verdict)
            if not self.handler.find_fix:
                self.build_range = self.build_range[: mid_point + 1]
            else:
                self.build_range = self.build_range[mid_point:]
            self.handler.build_bad(mid_point, self.build_range)
        elif verdict == "r":
            self.handler.build_retry(mid_point)
        elif verdict == "s":
            self.handler.build_skip(mid_point)
            self.history.add(self.build_range, mid_point, verdict)
            self.build_range = self.build_range.deleted(mid_point)
        elif verdict == "back":
            self.build_range = self.history[-1].build_range
        else:
            # user exit
            self.handler.user_exit(mid_point)
            return self.USER_EXIT
        return self.RUNNING


class Bisector(object):
    """
    Handle the logic of the bisection process, and report events to a given
    :class:`BisectorHandler`.
    """

    def __init__(
        self,
        fetch_config,
        test_runner,
        download_manager,
        dl_in_background=True,
        approx_chooser=None,
    ):
        self.fetch_config = fetch_config
        self.test_runner = test_runner
        self.download_manager = download_manager
        self.dl_in_background = dl_in_background
        self.approx_chooser = approx_chooser

    def bisect(self, handler, good, bad, **kwargs):
        if handler.find_fix:
            good, bad = bad, good
        build_range = handler.create_range(self.fetch_config, good, bad, **kwargs)

        return self._bisect(handler, build_range)

    def _bisect(self, handler, build_range):
        """
        Starts a bisection for a :class:`mozregression.build_range.BuildData`.
        """

        bisection = Bisection(
            handler,
            build_range,
            self.download_manager,
            self.test_runner,
            dl_in_background=self.dl_in_background,
            approx_chooser=self.approx_chooser,
        )

        previous_verdict = None

        while True:
            index = bisection.search_mid_point()
            result = bisection.init_handler(index)
            if result != bisection.RUNNING:
                return result
            if previous_verdict is None and handler.ensure_good_and_bad:
                if bisection.ensure_good_and_bad():
                    LOG.info("Good and bad builds are correct. Let's" " continue the bisection.")
                else:
                    return bisection.USER_EXIT
            bisection.handler.print_range(full=False)

            if previous_verdict == "back":
                index = bisection.history.pop(-1).index

            allow_bg_download = True
            if previous_verdict == "s":
                # disallow background download since we are not sure of what
                # to download next.
                allow_bg_download = False
                index = self.test_runner.index_to_try_after_skip(bisection.build_range)

            index_promise = None
            build_info = bisection.build_range[index]
            try:
                if previous_verdict != "r" and build_info:
                    # if the last verdict was retry, do not download
                    # the build. Futhermore trying to download if we are
                    # in background download mode would stop the next builds
                    # from downloading.
                    index_promise, build_info = bisection.download_build(
                        index, allow_bg_download=allow_bg_download
                    )

                if not build_info:
                    LOG.info("Unable to find build info. Skipping this build...")
                    verdict = "s"
                else:
                    try:
                        verdict = bisection.evaluate(build_info)
                    except LauncherError as exc:
                        # we got an unrecoverable error while trying
                        # to run the tested app. We can just fallback
                        # to skip the build.
                        LOG.info("Error: %s. Skipping this build..." % exc)
                        verdict = "s"
            finally:
                # be sure to terminate the index_promise thread in all
                # circumstances.
                if index_promise:
                    index = index_promise()
            previous_verdict = verdict
            result = bisection.handle_verdict(index, verdict)
            if result != bisection.RUNNING:
                return result
