import unittest
from unittest import TestCase
from Crawler import Crawler
import urlparse
import mock
import os
from bs4 import BeautifulSoup


class TestCrawler(TestCase):
    html_test_string = """
    <html>
        <body>
            <img src="http://sub.test.com/img.jpg" />
            <img src="/img2.png" />
            <img src="/a/img3.png" />
            <a href="http://test.com/a">A</a>
            <a href="http://sub,test.com/b">B</a>
            <a href="http://test.com/c">C</a>
            <a href="http://test.com/c">C2</a>
        </body>
    </html>
    """

    def test__init_url(self):
        bad_list = [
            "http://",
            "https:////",
            "?q=#1"
        ]

        good_list = [
            "http://www.google.com",
            "www.google.com"
            "//google.com",
            "www.http.google.https"
        ]
        for bad_url in bad_list:
            self.assertRaises(ValueError, Crawler, bad_url)
        for good_url in good_list:
            crawl = Crawler(good_url)
            self.assertIsInstance(crawl, Crawler)

    def test__nromalize_url(self):
        test_list = {
            "http://www.a.com#abc": "http://www.a.com/",
            "http://www.a.com/a/b/c": "http://www.a.com/a/b/c",

            # if no scheme is provided, urlsplit treats the domain name as the path
            # so we don't expect a trailing "/" after www.a.com
            "www.a.com?abc=123#abc": "://www.a.com?abc=123"
        }

        for test in test_list:
            usplit = urlparse.urlsplit(test)
            c = Crawler("http://mydomain.com")
            self.assertEqual(c._normalize_url(usplit), test_list[test])

    def test__parse_url(self):
        test_list = {
            "http://www.test2.com": None,
            "/a/b/c": "https://www.test.com/a/b/c",
            "/?q=1": "https://www.test.com/?q=1",
            "https://sub.test.com": None
        }

        for test in test_list:
            c = Crawler("https://www.test.com")
            self.assertEqual(c._parse_url(test), test_list[test])

    def test_crawl_limit(self):
        c = Crawler("http://a.com")
        c.SLEEP_TIME = 0

        def side_effect():
            c.process_q.pop(0)
        c._process_next_url = mock.Mock(side_effect=side_effect)
        c.render_sitemap = mock.Mock()

        c.URL_LIMIT = 10
        c.process_q = ["test"] * 5
        c.crawl()
        self.assertEqual(c._process_next_url.call_count, 5)

        c._process_next_url.call_count = 0
        c.process_q = ["test"] * 10
        c.URL_LIMIT = 5
        c.crawl()
        self.assertEqual(c._process_next_url.call_count, 5)

        c._process_next_url.call_count = 0
        c.process_q = ["test"] * 10
        c.URL_LIMIT = float("inf")
        c.crawl()
        self.assertEqual(c._process_next_url.call_count, 10)

    def test_render_sitemap(self):
        try:
            os.remove("sitemap.pdf")
        except OSError:
            pass

        self.assertEqual(os.path.exists("sitemap.pdf"), False)
        c = Crawler("http://a.com")
        c.render_sitemap()
        self.assertEqual(os.path.exists("sitemap.pdf"), True)

    def test__process_next_url_blacklist(self):
        c = Crawler("http://a.com")
        c.bad_urls = {"http://a.com/a/b/c/": True}
        c.process_q.append("http://a.com/a/b/c/")

        c._make_request = mock.Mock(return_value=None)
        c._process_html = mock.Mock()

        c._process_next_url()
        self.assertEqual(len(c.process_q), 1)
        self.assertEqual(len(c.bad_urls), 2)

        c._process_next_url()
        self.assertEqual(len(c.process_q), 0)
        self.assertEqual(len(c.bad_urls), 2)

        self.assertEqual(c._process_html.call_count, 0)

    def test__make_request(self):
        c = Crawler("http://test.com/")

        with mock.patch("Crawler.requests") as mock_requests:
            mock_requests.get.return_value = mock_response = mock.Mock()
            mock_response.text = True

            # Make sure it ignores non-200 responses
            mock_response.status_code = 404
            self.assertEqual(c._make_request(""), None)

            mock_response.status_code = 200

            # Make sure it ignores non-html responses
            mock_response.headers = {
                "content-type": "text/javascript"
            }
            self.assertEqual(c._make_request(""), None)

            mock_response.headers = {
                "content-type": "text/html"
            }
            # Make sure it ignores non-html responses
            self.assertEqual(c._make_request(""), True)

    def test__does_static_file_exist(self):
        exist_codes = [
            "200",
            "300",
            "304"
        ]
        nonexist_codes = [
            "404",
            "500"
        ]

        c = Crawler("http://test.com")

        with mock.patch("Crawler.requests") as mock_requests:
            mock_requests.head.return_value = mock_response = mock.Mock()

            for code in exist_codes:
                mock_response.status_code = code
                self.assertEqual(c._does_static_file_exist(""), True)

            for code in nonexist_codes:
                mock_response.status_code = code
                self.assertEqual(c._does_static_file_exist(""), False)

    def test__process_html_good_asset(self):
        c = Crawler("http://test.com")
        soup = BeautifulSoup(self.html_test_string)

        c._does_static_file_exist = mock.Mock(return_value=True)
        for asset in soup.find_all(True, src=True):
            c._process_html_asset(asset, "/")

        self.assertEqual(c._does_static_file_exist.call_count, 2)
        self.assertEqual(len(c.sitemap.nodes()), 3)
        self.assertEqual(len(c.sitemap.edges()), 2)

    def test__process_html_bad_asset(self):
        c = Crawler("http://test.com")
        soup = BeautifulSoup(self.html_test_string)

        c._does_static_file_exist = mock.Mock(return_value=False)
        for asset in soup.find_all(True, src=True):
            c._process_html_asset(asset, "/")

        self.assertEqual(c._does_static_file_exist.call_count, 2)
        self.assertEqual(len(c.sitemap.nodes()), 0)
        self.assertEqual(len(c.sitemap.edges()), 0)
        self.assertEqual(len(c.bad_urls), 2)

    def test__process_html_link(self):
        c = Crawler("http://test.com")
        soup = BeautifulSoup(self.html_test_string)

        for link in soup.find_all("a"):
            c._process_html_link(link, "/")

        self.assertEqual(len(c.sitemap.nodes()), 3)
        self.assertEqual(len(c.sitemap.edges()), 2)
        self.assertEqual(len(c.process_q), 3)

    def test__process_html(self):
        soup = BeautifulSoup(self.html_test_string)
        c = Crawler("http://test.com")
        c._process_html_asset = mock.Mock()
        c._process_html_link = mock.Mock()

        c._process_html(soup)
        self.assertEqual(c._process_html_asset.call_count, 3)
        self.assertEqual(c._process_html_link.call_count, 4)

if __name__ == "__main__":
    unittest.main()