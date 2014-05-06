crawler-example
===============
This is a simple project I wrote for an interview. The assignment text is as follows:
>We'd like you to write a web crawler in a modern language (something like Ruby, Python, Go, or Coffeescript).
>It should be limited to one domain - so when crawling domain.com it would crawl all pages within the domain.com domain, but not follow links to Facebook or Instagram accounts or subdomains like cloud.domain.com.
>Given a URL, it should output a site map, showing which static assets each page depends on, and the links between pages. Choose the most appropriate data structure to store & display this site map.
>Build this as you would build something for production - it's fine if you don't finish everything, but focus on code quality and write tests. We're interested in how you code and how you test your code.

This was my first foray into any sort of unittesting so best practices might not have been followed (because I don't know what they are yet).

Also, some progress and informational print statements were left in so the program isn't a black box.

Usage
-----
usage: Crawler.py [-h][-l limit] [crawl_target]

<b>-l</b>: The number of URLs to crawl before stopping. Default is all URLs found on the site.

<b>crawl_target</b>: The crawl target. Must be a valid URL.

The crawler will then create a file called <b>sitemap.pdf</b> in the same directory. This will contain an image showing sitemap.

Requirements
------------
Python 2.7

BeautifuSoup (as the bs4 module) for HTML tidy  
NetworkX (as the networkx module) for a graph data structure  
MatPlotLib (as the matplotlib module) for drawing to an image  
Requests (as the requests module) for easy network requests  
Mock (as the mock module) for unit test mocking  
