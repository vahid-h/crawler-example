import requests
import requests.exceptions
import sys
import urlparse
import re
from bs4 import BeautifulSoup
import networkx as nx
import time
import matplotlib.pyplot as pyplot
from getopt import getopt, GetoptError

class Crawler():
    """Crawl a given domain for all linked URLs."""
    SLEEP_TIME = .500 # time between network requests in seconds
    URL_LIMIT = float("inf") # number of links to follow before stopping

    def __init__(self, url):
        # URLs that need to be crawled
        self.process_q = []
        # Sitemap represented as a NetworkX directed graph
        self.sitemap = nx.DiGraph()
        # Current URL being crawled
        self.current_url = ""
        # List of blacklisted URLs that were found to be non-valid
        self.bad_urls = {}
        # Original user entered url for crawling
        self.url = self._init_url(url)
        self.process_q.append(self.url)

    def _normalize_url(self, usplit):
        """
        Normalize url with everything except the fragment (ex. #jump_point).

        Paramters:
            usplit: (SplitResult) the output of urlparse.urlsplit

        Returns:
            (String) A normalized URL
        """
        url = usplit.scheme + "://" + usplit.netloc
        if usplit.path != "":
            url = url + usplit.path
        else:
            url = url + "/"
        if usplit.query != "":
            url = url + "?" + usplit.query
        return url

    def _init_url(self, url):
        """
        Initilize the user entered URL and check for malformation

        Paramters:
            url: (String) user entered url to crawl

        Returns:
            (String) A normalized URL

        Exceptions:
            ValueError: if the URL is malformed
        """
        if not re.match("(http|https)://", url):
            url = "http://" + url
        usplit = urlparse.urlsplit(url)
        if usplit.netloc == "":
            raise ValueError("Invalid URL specified for crawling")
        new_url = self._normalize_url(usplit)
        usplit = urlparse.urlsplit(new_url)
        self.domain = usplit.netloc
        return new_url

    def _parse_url(self, url):
        """
        Create a new URL by combining the given paramter with the original user entered URL

        Paramters:
            url: (String) full URL or URL fragment to be combined with the originally entered URL

        Returns:
            (String) A normalized combined URL
        """
        new_url = urlparse.urljoin(self.url, url)
        usplit = urlparse.urlsplit(new_url)
        if usplit.netloc != self.domain:
            return None

        return self._normalize_url(usplit)

    def crawl(self):
        """
        Crawls a site. The user entered site represents the seed. For every page crawled, any links
        found with the same domain name will be added to the process queue for crawling. The number
        of pages to crawl can be artifically limited by the user by passing in a number as the second
        paramter to the script (this become self.URL_LIMIT).

        Once the URL_LIMIT has been hit or all pages have been crawled, the graph is rendering into a
        visual graph in a PDF file.
        """
        while self.URL_LIMIT > 0 and len(self.process_q) > 0:
            self._process_next_url()
            time.sleep(self.SLEEP_TIME)
            self.URL_LIMIT -= 1

        print "Crawling done. Generating sitemap..."
        start = time.time()
        self.render_sitemap()
        print "Done rendering sitemap. Took " + str(time.time() - start) + " seconds"

    def render_sitemap(self):
        """Create a MatPlotLib graph from the NetworkX graph data structure."""
        pyplot.figure(figsize=(200, 200))
        pyplot.title("Crawling results for " + self.url)
        pos = nx.spring_layout(self.sitemap)
        nx.draw(self.sitemap, pos, with_labels=False, node_size=30, width=.75)
        for p in pos:
            pos[p][1] += 0.001 # raise text positions above node
        nx.draw_networkx_labels(self.sitemap, pos, font_size=8)
        pyplot.savefig("sitemap.pdf")

    def _process_next_url(self):
        """
        Decide which URL to crawl next and crawl it.

        The next URL in the process queue is compared to a blacklist. This blacklist represents
        URLs that returned a non-200 status code previously, or static assets that returned a
        non-2XX and non-3XX status code. If the next prospective URL is not on this list, a
        GET request for it is made and BeautifulSoup cleans the HTML up.
        """
        if len(self.process_q) == 0:
            return None

        self.current_url = self.process_q.pop(0)
        while self.current_url in self.bad_urls:
            print "Skipping blacklisted url: " + self.current_url
            if len(self.process_q) > 0:
                self.current_url = self.process_q.pop(0)
            else:
                return
        print "Processing next URL in queue: " + self.current_url
        print str(len(self.process_q)) + " URLS left"
        html = self._make_request(self.current_url)
        if html is None:
            print "Adding to the blacklist: " + self.current_url
            self.bad_urls[self.current_url] = True
        else:
            clean_html = BeautifulSoup(html)
            self._process_html(clean_html)

    def _make_request(self, url):
        """
        GETs the provided URL.

        A basic wrapper around the Requests library. Sometimes the URL fed to this function
        does not point to HTML. Instead it can be something like an image or CSS. The
        "conetent-type" header is looked at to prevent the parsing of these non-HTML entities.

        Paramters:
            url: (String) the URL to GET

        Returns:
             (String) the HTML text if the GET was successful
             (None) None if the GET was unsuccessful or the URL was invalid
        """
        try:
            r = requests.get(url, allow_redirects=True)
            if r.status_code != 200:
                print "Got status code " + str(r.status_code) + " from url: " + url
                return None
            # Stop parsing of any binary files that sneaked through as href pointers in <a> tags
            if r.headers["content-type"] != "text/html":
                return None
            return r.text
        except requests.exceptions.ConnectionError:
            print "Tried crawling bad url: " + url
            return None

    def _does_static_file_exist(self, url):
        """
        Make a HEAD request for a static asset to check for its existance

        Paramters:
            url: (String) the URL to HEAD

        Returns:
            (Bool) True if the HEAD returnes a 2XX or 3XX code
            (Bool) False if the HEAD returns a non-2XX and non-3XX code
        """
        try:
            r = requests.head(url)
            # Consider 2XX or 3XX codes success for the purpose of existence checking
            if not re.match("(2|3)\d\d", str(r.status_code)):
                print "Got status code " + str(r.status_code) + " from url: " + url
                return False
            return True
        except requests.exceptions.ConnectionError:
            print "Tried crawling bad url: " + url
            return False

    def _process_html_asset(self, asset, current_path):
        """
        Process static assets by checking if they exists and, if so, adding them to the graph.

        Static assets are never placed in the process queue.

        Parameters:
            asset: (bs4.element.Tag) a Tag object from bs4 representing a static asset
            current_path: (String) the URL path of the current URL being processed
        """
        src = self._parse_url(asset.get("src"))
        if src is not None:
            src_path = urlparse.urlsplit(src).path
            if not self.sitemap.has_edge(current_path, src_path) and not src in self.bad_urls:
                if self._does_static_file_exist(src):
                    self.sitemap.add_edge(current_path, src_path)
                else:
                    self.bad_urls[src] = True
                    print "Adding to the blacklist: " + src

    def _process_html_link(self, link, current_path):
        """
        Process anchor links by checking if an edge between the current and prospective URL
        already exists. If not, create the directed edge and add the prospective URL to
        the process queue.

        Paramters:
            link: (bs4.element.Tag) a Tag object from bs4 representing an <a> tag
            current_path: (String) the URL path of the current URL being processed
        """
        new_url = self._parse_url(link.get("href"))
        if new_url is not None:
            new_path = urlparse.urlsplit(new_url).path
            if (current_path != new_path and not self.sitemap.has_edge(current_path, new_path) and
                    not self.sitemap.has_node(new_path)):
                # add_edge will create the edge source or dest node if it doesn't exist
                self.sitemap.add_edge(current_path, new_path)
                self.process_q.append(new_url)
                print "Adding " + new_url + " to the queue"

    def _process_html(self, html_soup):
        """
        Process a page for both static assets and anchor links.

        Parameters:
            html_soup: (bs4.BeautifulSoup) a BeautifulSoup object
        """
        current_path = urlparse.urlsplit(self.current_url).path
        # static assets chosen as any tag with a src attribute
        for asset in html_soup.find_all(True, src=True):
           self._process_html_asset(asset, current_path)

        # anchor links
        for link in html_soup.find_all("a"):
            self._process_html_link(link, current_path)

def main():
    usage = "usage: Crawler.py [-h][-l limit] [crawl_target]"

    try:
        optlist, args = getopt(sys.argv[1:], "hl:", ["limit="])
    except GetoptError:
        print usage
        sys.exit(2)

    if len(args) > 0:
        domain = args[0]
    else:
        domain = raw_input("Enter a url to crawl:")

    crawler = Crawler(domain)

    for opt, arg in optlist:
        if opt == "-h":
            print usage
            sys.exit(0)
        if opt in ("-l", "--limit"):
            try:
                crawler.URL_LIMIT = int(arg)
            except ValueError:
                print "URL limit was not a valid number. Crawling whole site..."
                crawler.URL_LIMIT = float("inf")

    crawler.crawl()

if __name__ == "__main__":
    main()