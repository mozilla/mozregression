import unittest
from mock import patch, Mock
import datetime
import tempfile
import shutil
import os
import re
from mozregression import utils

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
    
    @patch('sys.stdout')
    def test_invalid_date(self, stdout):
        stdout_data = []
        stdout.write = lambda text: stdout_data.append(text)
        
        date = utils.get_date("invalid_format")
        self.assertIsNone(date)
        self.assertIn("Incorrect date format", ''.join(stdout_data))

class TestDownloadUrl(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tempdir)
    
    @patch('sys.stdout')
    def test_already_downloaded(self, stdout):
        stdout_data = []
        stdout.write = lambda text: stdout_data.append(text)
        
        fname = os.path.join(self.tempdir, 'something')
        with open(fname, 'w') as f:
            f.write("1")
        
        utils.download_url('', fname)
        
        self.assertIn("Using local file", "".join(stdout_data))
    
    @patch('requests.get')
    @patch('sys.stdout')
    def test_already_downloaded(self, stdout, get):
        stdout_data = []
        stdout.write = lambda text: stdout_data.append(text)
        
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
        self.assertIn("Downloading build from: http://toto", ''.join(stdout_data))


class TestRelease(unittest.TestCase):
    def test_valid_release_to_date(self):
        date = utils.date_of_release(8)
        self.assertEquals(date, "2011-08-16")
        date = utils.date_of_release(34)
        self.assertEquals(date, "2014-06-09")
        date = utils.date_of_release(39)
        self.assertEquals(date, "2015-02-16")

    def test_invalid_release_to_date(self):
        date = utils.date_of_release(4)
        self.assertEquals(date, None)
        date = utils.date_of_release(441)
        self.assertEquals(date, None)

    def test_valid_decoration(self):
        @utils.accept_release(2, 4)
        def func(self, param1, good_date, param2, bad_date):
            res1, res2 = None, None
            if type(good_date) is str:
                r = re.compile(r'(\d{4})\-(\d{1,2})\-(\d{1,2})')
                matched = r.match(good_date)
                if matched:
                    res1 = good_date
            if type(bad_date) is str:
                matched = r.match(bad_date)
                if matched:
                    res2 = bad_date
            return res1, res2
        res = func(self, None, "2011-04-12", None, 5)
        self.assertEquals(res, ("2011-04-12", "2011-04-12"))
        res = func(self, None, 28, None, "1011-01-01")
        self.assertEquals(res, ("2013-12-09", "1011-01-01"))
        res = func(self, None, 30, None, 40)
        self.assertEquals(res, ("2014-03-17", "2015-03-30"))


if __name__ == '__main__':
    unittest.main()
