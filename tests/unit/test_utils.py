import unittest
from mock import patch, Mock
import datetime
import tempfile
import shutil
import os
from mozregression import utils, errors

class TestUrlLinks(unittest.TestCase):
    @patch('requests.get')
    def test_url_no_links(self, get):
        get.return_value = Mock(text='')
        self.assertEquals(utils.url_links(''), [])
    
    @patch('requests.get')
    def test_url_with_links(self, get):
        get.return_value = Mock(text="""
        <body>
        <a href="thing/">thing</a>
        <a href="thing2/">thing2</a>
        </body>
        """)
        self.assertEquals(utils.url_links(''), ['thing/', 'thing2/'])
    
    @patch('requests.get')
    def test_url_with_links_regex(self, get):
        get.return_value = Mock(text="""
        <body>
        <a href="thing/">thing</a>
        <a href="thing2/">thing2</a>
        </body>
        """)
        self.assertEquals(utils.url_links('', regex="thing2.*"), ['thing2/'])

class TestGetDate(unittest.TestCase):
    def test_valid_date(self):
        date = utils.get_date("2014-07-05")
        self.assertEquals(date, datetime.date(2014, 7, 5))

    def test_invalid_date(self):
        self.assertRaises(errors.DateFormatError, utils.get_date, "invalid_format")

class TestDownloadUrl(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir)

    @patch('requests.get')
    def test_download(self, get):
        self.data = """
        hello,
        this is a response.
        """ * (1024 * 16)

        def iter_content(chunk_size=1):
            rest = self.data
            while rest:
                chunk = rest[:chunk_size]
                rest = rest[chunk_size:]
                yield chunk

        response = Mock(headers={'Content-length': str(len(self.data))},
                        iter_content=iter_content)
        get.return_value = response

        fname = os.path.join(self.tempdir, 'some.content')
        utils.download_url('http://toto', fname)

        self.assertEquals(self.data, open(fname).read())

class TestGetBuildUrl(unittest.TestCase):
    def test_for_linux(self):
        self.assertEqual(utils.get_build_regex('test', 'linux', 32), r'test.*linux-i686\.tar.bz2')
        self.assertEqual(utils.get_build_regex('test', 'linux', 64), r'test.*linux-x86_64\.tar.bz2')
        self.assertEqual(utils.get_build_regex('test', 'linux', 64, with_ext=False), r'test.*linux-x86_64')

    def test_for_win(self):
        self.assertEqual(utils.get_build_regex('test', 'win', 32), r'test.*win32\.zip')
        self.assertEqual(utils.get_build_regex('test', 'win', 64), r'test.*win64-x86_64\.zip')
        self.assertEqual(utils.get_build_regex('test', 'win', 64, with_ext=False), r'test.*win64-x86_64')

    def test_for_mac(self):
        self.assertEqual(utils.get_build_regex('test', 'mac', 32), r'test.*mac.*\.dmg')
        self.assertEqual(utils.get_build_regex('test', 'mac', 64), r'test.*mac.*\.dmg')
        self.assertEqual(utils.get_build_regex('test', 'mac', 64, with_ext=False), r'test.*mac.*')

class TestRelease(unittest.TestCase):
    def test_valid_release_to_date(self):
        date = utils.date_of_release(8)
        self.assertEquals(date, "2011-08-16")
        date = utils.date_of_release(15)
        self.assertEquals(date, "2012-06-05")
        date = utils.date_of_release(34)
        self.assertEquals(date, "2014-09-02")

    def test_invalid_release_to_date(self):
        date = utils.date_of_release(4)
        self.assertEquals(date, None)
        date = utils.date_of_release(441)
        self.assertEquals(date, None)


if __name__ == '__main__':
    unittest.main()
