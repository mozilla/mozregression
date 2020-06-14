from __future__ import absolute_import

import unittest

from mock import Mock, patch

from mozregression import network


class TestUrlLinks(unittest.TestCase):
    @patch("requests.get")
    def test_url_no_links(self, get):
        get.return_value = Mock(text="")
        self.assertEqual(network.url_links(""), [])

    @patch("requests.get")
    def test_url_with_links(self, get):
        get.return_value = Mock(
            text="""
        <body>
        <a href="thing/">thing</a>
        <a href="thing2/">thing2</a>
        </body>
        """
        )
        self.assertEqual(network.url_links(""), ["thing/", "thing2/"])

    @patch("requests.get")
    def test_url_with_links_regex(self, get):
        get.return_value = Mock(
            text="""
        <body>
        <a href="thing/">thing</a>
        <a href="thing2/">thing2</a>
        </body>
        """
        )
        self.assertEqual(network.url_links("", regex="thing2.*"), ["thing2/"])

    @patch("requests.get")
    def test_url_with_absolute_links(self, get):
        get.return_value = Mock(
            text="""
        <body>
        <a href="/useless/thing/">thing</a>
        <a href="/useless/thing2">thing2</a>
        </body>
        """
        )
        self.assertEqual(network.url_links(""), ["/useless/thing/", "/useless/thing2"])


def test_set_http_session():
    try:
        with patch("requests.Session") as Session:
            session = Session.return_value = Mock()
            session_get = session.get

            network.set_http_session(get_defaults={"timeout": 5})

        assert session == network.get_http_session()
        # timeout = 5 will be passed to the original get method as a default
        session.get("http://my-ul")
        session_get.assert_called_with("http://my-ul", timeout=5)
        # if timeout is defined, it will override the default
        session.get("http://my-ul", timeout=10)
        session_get.assert_called_with("http://my-ul", timeout=10)

    finally:
        # remove the global session to not impact other tests
        network.SESSION = None


if __name__ == "__main__":
    unittest.main()
