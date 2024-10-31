# web-crawler
## Project description
The project represents a crawler program that is capable of scanning a given website in parallel. It is written in Python without using external libraries. It generates a report with the following information:

<ol>
  <li> A list of all the links under the given website and their depth (where "depth" means: the number of "clicks" away from the home page). If a link on some of pages references some external resource, it's included into the report, but the crawler doesn't proceed to the external resource. The depth of the link is not necessarily guaranteed to be minimal possible (in case there are two routes to the same link), but the first that crawlers meets (a link added to the list once won't be added again).
  </li>
  <li>
    A list of all the broken links. For each link in the list the report includes the status code (for http errors) or reason (for URL errors).
  </li>
  <li>
    A list of broken image links across pages.
  </li>
  <li>
    A list of duplicated links and links that point to the same image.
  </li>
</ol>

<b>How to compile:</b> python3 crawler.py </br>
<b>Input:</b> the URL of the website to parse. It can be set in MAIN_URL global const. </br>
<b>Output:</b> "report.txt" file in the current directory.

## Implementation details
<ol>
  <li>
    For achieving parallelism I used multiprocessing approach. It allows Python to run several instructions at the same time, in comparison to councurrency.
The worker processes are managed by Pool. Using pool increases performance, because it removes overhead of creating and destroying processes for every new task.
When the current URL is processed, a new task for each URL on the page is created and queued for execution.
  </li>
  <li>
    The HTML by the URL is parsed using LinkParser, that is inhereted from HTMLParser. It works with start tags and finds the links stored inside <a> tags.
  </li>
  <li>
    If the resource isn't responding, generate_html() tries to wait and call the resource again. If it doesn't respond several times in a row, the link is considered broken.
So, the bottleneck causing the decreasing of performance is awaiting the response of the server, especially for broken links.
(The program works several minutes on the given test website)
  </li>
  <li>
    The number of worker processes is chosen depending on the number of CPU cores of the current device running the app.
Comparison with one-process case shows significant improvement in performance for the multi-process case even for small amounts of data.
  </li>
</ol>

## Testing and data pitfalls
The program is tested using the resource https://crawler-test.com. </br>
There are several specific data features for the website, for example, some links are redirecting. If the link redirects to another source, the program doesn't include the initial link, but only the resource that it links to. It helps to avoid revisiting the same source and parsing contents of external resources.


