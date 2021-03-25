from __future__ import absolute_import

import datetime
import re
import unittest

from mock import Mock, patch

from mozregression import errors, fetch_build_info, fetch_configs

from .test_fetch_configs import create_push


class TestInfoFetcher(unittest.TestCase):
    def setUp(self):
        fetch_config = fetch_configs.create_config("firefox", "linux", 64, "x86_64")
        self.info_fetcher = fetch_build_info.InfoFetcher(fetch_config)

    @patch("requests.get")
    def test__fetch_txt_info(self, get):
        response = Mock(
            text="20141101030205\nhttps://hg.mozilla.org/\
mozilla-central/rev/b695d9575654\n"
        )
        get.return_value = response
        expected = {
            "repository": "https://hg.mozilla.org/mozilla-central",
            "changeset": "b695d9575654",
        }
        self.assertEqual(self.info_fetcher._fetch_txt_info("http://foo.txt"), expected)

    @patch("requests.get")
    def test__fetch_txt_info_old_format(self, get):
        response = Mock(text="20110126030333 e0fc18b3bc41\n")
        get.return_value = response
        expected = {
            "changeset": "e0fc18b3bc41",
        }
        self.assertEqual(self.info_fetcher._fetch_txt_info("http://foo.txt"), expected)


class TestNightlyInfoFetcher(unittest.TestCase):
    def setUp(self):
        fetch_config = fetch_configs.create_config("firefox", "linux", 64, "x86_64")
        self.info_fetcher = fetch_build_info.NightlyInfoFetcher(fetch_config)

    @patch("mozregression.fetch_build_info.url_links")
    def test__find_build_info_from_url(self, url_links):
        url_links.return_value = [
            "http://foo/file1.txt.gz",
            "http://foo/file2.txt",
            "http://foo/firefox01linux-x86_64.txt",
            "http://foo/firefox01linux-x86_64.tar.bz2",
        ]
        expected = {
            "build_txt_url": "http://foo/firefox01linux-x86_64.txt",
            "build_url": "http://foo/firefox01linux-x86_64.tar.bz2",
        }
        builds = []
        self.info_fetcher._fetch_build_info_from_url("http://foo", 0, builds)
        self.assertEqual(builds, [(0, expected)])

    @patch("mozregression.fetch_build_info.url_links")
    def test__find_build_info_incomplete_data_raises_exception(self, url_links):
        # We want to find a valid match for one of the build file regexes,
        # build_info_regex. But we will make the build filename regex fail. This
        # could happen if, for example, the name of the build file changed in
        # the archive but our tool is still searching with the old build file
        # regex.
        url_links.return_value = [
            "validinfofilename.txt",
            "invalidbuildfilename.tar.bz2",
        ]
        # build_regex doesn't match any of the files in the web directory.
        self.info_fetcher.build_regex = re.compile("xxx")
        # But build_info_regex does match one file in the directory.
        self.info_fetcher.build_info_regex = re.compile("validinfofilename.txt")

        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher._fetch_build_info_from_url("some-url", 1, [])

    @patch("mozregression.fetch_build_info.url_links")
    def test__get_url(self, url_links):
        url_links.return_value = [
            fetch_configs.ARCHIVE_BASE_URL
            + "/firefox/nightly/2014/11/2014-11-01-03-02-05-mozilla-central/",
            fetch_configs.ARCHIVE_BASE_URL + "/firefox/nightly/2014/11/2014-11-01-03-02-05-foo/",
            fetch_configs.ARCHIVE_BASE_URL + "/firefox/nightly/2014/11/foo",
            fetch_configs.ARCHIVE_BASE_URL + "/firefox/nightly/2014/11/bar/",
        ]
        urls = self.info_fetcher._get_urls(datetime.date(2014, 11, 1))
        self.assertEqual(
            urls[0],
            fetch_configs.ARCHIVE_BASE_URL
            + "/firefox/nightly/2014/11/2014-11-01-03-02-05-mozilla-central/",
        )
        urls = self.info_fetcher._get_urls(datetime.date(2014, 11, 2))
        self.assertEqual(urls, [])

    def test_find_build_info(self):
        get_urls = self.info_fetcher._get_urls = Mock(
            return_value=[
                "https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-08-02-05-mozilla-central/",
                "https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-04-02-05-mozilla-central/",
                "https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-03-02-05-mozilla-central",
                "https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-02-02-05-mozilla-central/",
                "https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-01-02-05-mozilla-central/",
            ]
        )

        def my_find_build_info(url, index, lst):
            # say only the last build url is invalid
            if url in get_urls.return_value[:-1]:
                return
            lst.append((index, {"build_txt_url": url, "build_url": url}))

        self.info_fetcher._fetch_build_info_from_url = Mock(side_effect=my_find_build_info)
        self.info_fetcher._fetch_txt_info = Mock(return_value={})
        result = self.info_fetcher.find_build_info(datetime.date(2014, 11, 15))
        # we must have found the last build url valid
        self.assertEqual(result.build_url, get_urls.return_value[-1])

    def test_find_build_info_no_data(self):
        self.info_fetcher._get_urls = Mock(return_value=[])
        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher.find_build_info(datetime.date(2014, 11, 15))


class TestNightlyInfoFetcher2(unittest.TestCase):
    def setUp(self):
        fetch_config = fetch_configs.create_config("firefox", "win", 64, "x86_64")
        self.info_fetcher = fetch_build_info.NightlyInfoFetcher(fetch_config)

    @patch("mozregression.fetch_build_info.url_links")
    def test__find_build_info_from_url(self, url_links):
        url_links.return_value = [
            "http://foo/firefox/jsshell-win64.zip",
            "http://foo/file1.txt.zip",
            "http://foo/file2.txt",
            "http://foo/firefox01linux-x86_64.txt",
            "http://foo/firefox01linux-x86_64.tar.bz2",
            "http://foo/firefox01win64.txt",
            "http://foo/firefox01win64.zip",
        ]
        expected = {
            "build_txt_url": "http://foo/firefox01win64.txt",
            "build_url": "http://foo/firefox01win64.zip",
        }
        builds = []
        self.info_fetcher._fetch_build_info_from_url("http://foo", 0, builds)
        self.assertEqual(builds, [(0, expected)])


class TestIntegrationInfoFetcher(unittest.TestCase):
    def setUp(self):
        self.fetch_config = fetch_configs.create_config("firefox", "linux", 64, "x86_64")

    @patch("taskcluster.Index")
    @patch("taskcluster.Queue")
    def test_find_build_info(self, Queue, Index):
        Index.return_value.findTask.return_value = {"taskId": "task1"}
        Queue.return_value.status.return_value = {
            "status": {
                "runs": [{"state": "completed", "runId": 0, "resolved": "2015-06-01T22:13:02.115Z"}]
            }
        }
        Queue.return_value.listArtifacts.return_value = {
            "artifacts": [
                # return two valid artifact names
                {"name": "firefox-42.0a1.en-US.linux-x86_64.tar.bz2"},
                {"name": "firefox-42.0a1.en-US.linux-x86_64.txt"},
            ]
        }
        Queue.return_value.buildUrl.return_value = (
            "http://firefox-42.0a1.en-US.linux-x86_64.tar.bz2"
        )
        self.info_fetcher = fetch_build_info.IntegrationInfoFetcher(self.fetch_config)
        self.info_fetcher._fetch_txt_info = Mock(return_value={"changeset": "123456789"})

        result = self.info_fetcher.find_build_info(create_push("123456789", 1))
        self.assertEqual(result.build_url, "http://firefox-42.0a1.en-US.linux-x86_64.tar.bz2")
        self.assertEqual(result.changeset, "123456789")
        self.assertEqual(result.build_type, "integration")

    @patch("taskcluster.Index")
    def test_find_build_info_no_task(self, Index):
        Index.findTask = Mock(side_effect=fetch_build_info.TaskclusterFailure)
        self.info_fetcher = fetch_build_info.IntegrationInfoFetcher(self.fetch_config)
        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher.find_build_info(create_push("123456789", 1))

    @patch("taskcluster.Index")
    @patch("taskcluster.Queue")
    def test_get_valid_build_no_artifacts(self, Queue, Index):
        def find_task(route):
            return {"taskId": "task1"}

        def status(task_id):
            return {
                "status": {
                    "runs": [
                        {"state": "completed", "runId": 0, "resolved": "2015-06-01T22:13:02.115Z"}
                    ]
                }
            }

        def list_artifacts(taskid, run_id):
            return {"artifacts": []}

        Index.findTask = find_task
        Queue.status = status
        Queue.listArtifacts = list_artifacts

        self.info_fetcher = fetch_build_info.IntegrationInfoFetcher(self.fetch_config)
        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher.find_build_info(create_push("123456789", 1))

    @patch("mozregression.json_pushes.JsonPushes.push")
    def test_find_build_info_check_changeset_error(self, push):
        push.side_effect = errors.MozRegressionError
        self.info_fetcher = fetch_build_info.IntegrationInfoFetcher(self.fetch_config)
        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher.find_build_info(
                "123456789",
            )
        push.assert_called_with("123456789")
