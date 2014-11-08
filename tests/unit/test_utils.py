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
