import unittest
import datetime
from mock import patch, Mock

from mozregression import fetch_build_info, fetch_configs, errors


class TestInfoFetcher(unittest.TestCase):
    def setUp(self):
        fetch_config = fetch_configs.create_config('firefox', 'linux', 64)
        self.info_fetcher = fetch_build_info.InfoFetcher(fetch_config)

    @patch('requests.get')
    def test__fetch_txt_info(self, get):
        response = Mock(text="20141101030205\nhttps://hg.mozilla.org/\
mozilla-central/rev/b695d9575654\n")
        get.return_value = response
        expected = {
            'repository': 'https://hg.mozilla.org/mozilla-central',
            'changeset': 'b695d9575654',
        }
        self.assertEqual(self.info_fetcher._fetch_txt_info('http://foo.txt'),
                         expected)

    @patch('requests.get')
    def test__fetch_txt_info_old_format(self, get):
        response = Mock(text="20110126030333 e0fc18b3bc41\n")
        get.return_value = response
        expected = {
            'changeset': 'e0fc18b3bc41',
        }
        self.assertEqual(self.info_fetcher._fetch_txt_info('http://foo.txt'),
                         expected)


class TestNightlyInfoFetcher(unittest.TestCase):
    def setUp(self):
        fetch_config = fetch_configs.create_config('firefox', 'linux', 64)
        self.info_fetcher = fetch_build_info.NightlyInfoFetcher(fetch_config)

    @patch('mozregression.fetch_build_info.url_links')
    def test__find_build_info_from_url(self, url_links):
        url_links.return_value = [
            'file1.txt.gz',
            'file2.txt',
            'firefox01linux-x86_64.txt',
            'firefox01linux-x86_64.tar.bz2',
        ]
        expected = {
            'build_txt_url': 'http://foo/firefox01linux-x86_64.txt',
            'build_url': 'http://foo/firefox01linux-x86_64.tar.bz2',
        }
        self.assertEqual(
            self.info_fetcher._fetch_build_info_from_url('http://foo'),
            expected
        )

    @patch('mozregression.fetch_build_info.url_links')
    def test__get_url(self, url_links):
        url_links.return_value = [
            '2014-11-01-03-02-05-mozilla-central/',
            '2014-11-01-03-02-05-foo/',
            'foo',
            'bar/'
        ]
        urls = self.info_fetcher._get_urls(datetime.date(2014, 11, 01))
        self.assertEqual(urls[0], 'https://archive.mozilla.org/pub/mozilla.org/\
firefox/nightly/2014/11/2014-11-01-03-02-05-mozilla-central/')
        urls = self.info_fetcher._get_urls(datetime.date(2014, 11, 02))
        self.assertEqual(urls, [])

    def test_find_build_info(self):
        get_urls = self.info_fetcher._get_urls = Mock(return_value=[
            'https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-08-02-05-mozilla-central/',
            'https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-04-02-05-mozilla-central/',
            'https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-03-02-05-mozilla-central',
            'https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-02-02-05-mozilla-central/',
            'https://archive.mozilla.org/pub/mozilla.org/\
bar/nightly/2014/11/2014-11-15-01-02-05-mozilla-central/',
        ])

        def my_find_build_info(url):
            # say only the last build url is invalid
            if url in get_urls.return_value[:-1]:
                return {}
            return {
                'build_txt_url': url,
                'build_url': url,
            }
        self.info_fetcher._fetch_build_info_from_url = Mock(
            side_effect=my_find_build_info
        )
        self.info_fetcher._fetch_txt_info = Mock(return_value={})
        result = self.info_fetcher.find_build_info(datetime.date(2014, 11, 15))
        # we must have found the last build url valid
        self.assertEqual(result, {
            'build_txt_url': get_urls.return_value[-1],
            'build_url': get_urls.return_value[-1],
        })

    def test_find_build_info_no_data(self):
        self.info_fetcher._get_urls = Mock(return_value=[])
        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher.find_build_info(datetime.date(2014, 11, 15))


class TestInboundInfoFetcher(unittest.TestCase):
    def setUp(self):
        fetch_config = fetch_configs.create_config('firefox', 'linux', 64)
        self.info_fetcher = fetch_build_info.InboundInfoFetcher(fetch_config)

    def test_find_build_info(self):
        # patch task cluster related stuff

        def find_task(route):
            return {'taskId': 'task1'}

        def list_artifacts(taskid):
            return {"artifacts": [
                # return two valid artifact names
                {'name': 'firefox-42.0a1.en-US.linux-x86_64.tar.bz2'},
                {'name': 'firefox-42.0a1.en-US.linux-x86_64.txt'},
            ]}

        def build_url(bname, taskid, name):
            return 'http://' + name

        self.info_fetcher.index.findTask = Mock(side_effect=find_task)
        self.info_fetcher.queue.listLatestArtifacts = \
            Mock(side_effect=list_artifacts)
        self.info_fetcher.queue.buildUrl = Mock(side_effect=build_url)
        self.info_fetcher._fetch_txt_info = \
            Mock(return_value={'changeset': '123456789'})

        result = self.info_fetcher.find_build_info('123456789')
        self.assertEqual(result, {
            'build_txt_url': 'http://firefox-42.0a1.en-US.linux-x86_64.txt',
            'build_url': 'http://firefox-42.0a1.en-US.linux-x86_64.tar.bz2',
            'changeset': '123456789',
        })

    def test_find_build_info_no_task(self):
        self.info_fetcher.index.findTask = Mock(
            side_effect=fetch_build_info.TaskclusterFailure
        )
        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher.find_build_info('123456789')

    def test_get_valid_build_no_artifacts(self):
        def find_task(route):
            return {'taskId': 'task1'}

        def list_artifacts(taskid):
            return {"artifacts": []}

        self.info_fetcher.index.findTask = Mock(side_effect=find_task)
        self.info_fetcher.queue.listLatestArtifacts = \
            Mock(side_effect=list_artifacts)

        with self.assertRaises(errors.BuildInfoNotFound):
            self.info_fetcher.find_build_info('123456789')
