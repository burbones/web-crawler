# Some link on the website can have several routes to get to.
# The number of "clicks" away from the home page can be different between this routes.
# As there is no requirement that the number of clicks needs to be minimal of all possible,
# my algorithm returns the depth for the first route encountered.
# After the link was visited, it will never be visited again. It also prevents endless loops.

import time
import hashlib
import urllib.request
from collections import deque
from multiprocessing import Manager, Pool
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from http.client import IncompleteRead
 
# Global consts
MAIN_URL = r"https://crawler-test.com/"
ABSOLUTE_PATH_START = r"http"
 
REPORT_FILE_PATH = "report.txt"
 
class LinkParser(HTMLParser):
	"""
	Parser for text files in HTML format. The handle_starttag method is used to extract links from a-tags.
	"""
 
	# Constructor
	def __init__(self, url):
		super().__init__()
		self.url = url
		self.links = []
		self.image_sources = []
 
	# Overrides parent method
	# attrs contains (name, value) pairs of attributes inside the starttag
	def handle_starttag(self, tag, attrs):
		HREF = "href"
		SRC = "src"
 
		if tag.lower() == 'a':
			for attribute_tuple in attrs:
				if attribute_tuple[0] == HREF:
					absolute_path = urljoin(self.url, attribute_tuple[1])
					self.links.append(absolute_path)
 
		elif tag.lower() == 'img':
			for attribute_tuple in attrs:
				if attribute_tuple[0] == SRC:
					absolute_path = urljoin(self.url, attribute_tuple[1])
					self.image_sources.append(absolute_path)
 
def generate_html(url):
	"""
	Returns the contents of the URL in text format.
	"""
	retries = 3
	timeout = 5
 
	for attempt in range(retries):
		try:
			raw_contents = urlopen(url, timeout=timeout)
			url = raw_contents.geturl()
			return raw_contents.read().decode("utf-8"), url
		except HTTPError as err:
			raise
		except URLError as err:
			if attempt < retries - 1:
				time.sleep(1)
			else:
				raise
		except IncompleteRead as err:
			if attempt < retries - 1:
				time.sleep(1)
		except Exception:
			pass
 
def process_link(args):
	"""
	Processes the current link: checks if it's broken, if not - evokes processing of child links.
	"""
	url, cur_depth, all_links_depths, broken_links, image_links, hash_images, all_links_lock, broken_links_lock, image_link_lock, hash_images_lock, links_to_parse = args
	
	# adding a new link to the list of all links
	with all_links_lock:
		if url not in all_links_depths:
			all_links_depths[url] = cur_depth
		else:
			return
 
	# processing links and images on the page
	try:
		res = generate_html(url)
		if res:
			html, url = res
		
		# if the url was redirecting to some external website, the page shouldn't be parsed
		if url.startswith(MAIN_URL):
			parser = LinkParser(url)
			try:
				parser.feed(html)
			except Exception:
				pass
 
			for link in parser.links:
				with all_links_lock:
					if link not in all_links_depths and (link.startswith(MAIN_URL) or not link.startswith(ABSOLUTE_PATH_START)):
						links_to_parse.append((link, cur_depth + 1))
 
			for img in parser.image_sources:
 				# not synchronized access - can lead to unnecessary loading of data, but prevents locking for the whole load time 	
				if img not in image_links:
					is_broken = False
					try:
						image_data = download_image_data(img)
						hash_code = hashlib.sha256(image_data).hexdigest()
						
						with hash_images_lock:
							hash_images[img] = hash_code
					except:
						is_broken = True
							
					with image_link_lock:
						if is_broken:
							image_links[img] = -1
						else:
							image_links[img] = image_links.get(img, 0) + 1
				
				# if img is already in the dictionary, no need to try to load it again
				else:
					if image_links[img] != -1:
						image_links[img] = image_links.get(img) + 1
 
	except HTTPError as err:
		if err.code in range(400, 600):
			with broken_links_lock:
				broken_links[url] = err.code
	except URLError as err:
		with broken_links_lock:
			broken_links[url] = err.reason
 
def scan_website(url):
	"""
	Scans the given website for all links, broken links.
	"""
	cur_depth = 0
 
 	# setting up the Process Pool
	manager = Manager()
	links_to_parse = manager.list([(url, cur_depth)])
	all_links_depths = manager.dict()					# contains info about URLs and their "depth"
	broken_links = manager.dict()
	image_links = manager.dict()		# contains info of how many times the link was encountered, -1 if it's broken
	hash_images = manager.dict()		# contains hash values of images to check for equal
	
	all_links_lock = manager.Lock()
	broken_links_lock = manager.Lock()
	image_link_lock = manager.Lock()
	hash_images_lock = manager.Lock()
 
	with Pool() as pool:
		task_list = []
		while links_to_parse:
			url, cur_depth = links_to_parse.pop(0)
			task_list.append(pool.apply_async(process_link,
												((url, cur_depth,
													all_links_depths, broken_links, image_links, hash_images, 
													all_links_lock, broken_links_lock, image_link_lock, hash_images_lock,
				 									links_to_parse),)))

			# if no links to parse - waiting for another task to complete
			while task_list and not links_to_parse:
				task_list.pop().get()

		pool.close()
		pool.join()
 
	return all_links_depths, broken_links, image_links, hash_images

def download_image_data(url):
	with urllib.request.urlopen(url) as response:
		try:
			return response.read()
		except Exception:
			raise

def write_report_all(report_file, all_links_depths):
	report_file.write("All links and depth:\n")
	for cur_url in all_links_depths:
		report_file.write(cur_url + ", depth: " + str(all_links_depths[cur_url]) + "\n")
		
def write_report_broken_links(report_file, broken_links):
	report_file.write("\nBroken links:\n")
	for cur_broken_url in broken_links:
		report_file.write(cur_broken_url + ", err_code: " + str(broken_links[cur_broken_url]) + "\n")
			
def write_report_broken_image_links(report_file, image_links):
	report_file.write("\nBroken image links:\n")
	for cur_img_url in image_links:
		if image_links[cur_img_url] == -1:
			report_file.write(cur_img_url + "\n")
				
def write_report_duplicate_image_links(report_file, image_links):
	report_file.write("\nImage links that appear more than once:\n")
	for cur_img_url in image_links:
		if image_links[cur_img_url] > 1:
			report_file.write(cur_img_url + ", appears " + str(image_links[cur_img_url]) + " times\n")

def write_report_same_hash(report_file, image_links, hash_images):
	report_file.write("\nDifferent links, same image (hash):\n")
	hashcodes = {}
	for cur_img_url in hash_images:
		hash_key = hash_images[cur_img_url]
			
		if hash_key not in hashcodes:
			hashcodes[hash_key] = set()
				
		hashcodes[hash_key].add(cur_img_url)
			
	for key in hashcodes:
		if len(hashcodes[key]) > 1:
			for elem in hashcodes[key]:
				report_file.write(elem + " ")
			report_file.write("\n")

def write_report(all_links_depths, broken_links, image_links, hash_images):
	"""
	Writes the report to the file.
	"""
	with open(REPORT_FILE_PATH, "a") as report_file:
		write_report_all(report_file, all_links_depths)
		write_report_broken_links(report_file, broken_links)
		write_report_broken_image_links(report_file, image_links)
		write_report_duplicate_image_links(report_file, image_links)
		write_report_same_hash(report_file, image_links, hash_images)
 
if __name__ == "__main__":
	all_links_depths, broken_links, image_links, hash_images = scan_website(MAIN_URL)
	write_report(all_links_depths, broken_links, image_links, hash_images)
