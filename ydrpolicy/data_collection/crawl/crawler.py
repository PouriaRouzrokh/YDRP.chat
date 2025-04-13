# ydrpolicy/data_collection/crawl/crawler.py

import heapq
import json
import logging
import os
import re
import signal
import sys
import time
import urllib.parse
import datetime # Import datetime
import shutil # Import shutil
from types import SimpleNamespace
from typing import List, Optional, Tuple, Dict, Any # Added Dict, Any

import pandas as pd
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ydrpolicy.data_collection.crawl.crawler_state import CrawlerState
# Use aliases for clarity
from ydrpolicy.data_collection.crawl.processors.document_processor import (
    convert_to_markdown as crawl_convert_to_md,
    download_document as crawl_download_doc,
    html_to_markdown
)
# Import updated pdf processor that returns path and timestamp
from ydrpolicy.data_collection.crawl.processors.pdf_processor import \
    pdf_to_markdown as crawl_pdf_to_md
# Restore LLM processor and prompts
from ydrpolicy.data_collection.crawl.processors.llm_processor import \
    analyze_content_for_policies
from ydrpolicy.data_collection.crawl.processors import llm_prompts as crawler_llm_prompts

# Initialize logger
logger = logging.getLogger(__name__)

class YaleCrawler:
    """Class for crawling Yale Medicine webpages and documents using priority-based algorithm."""

    def __init__(
            self,
            config: SimpleNamespace,
        ):
        """Initialize the crawler."""
        self.visited_urls = set()
        self.priority_queue: List[Tuple[float, str, int]] = []
        self.driver: Optional[webdriver.Chrome] = None
        self.current_url: Optional[str] = None
        self.current_depth: int = 0
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.state_manager = CrawlerState(os.path.join(config.PATHS.RAW_DATA_DIR, "state"), self.logger)
        self.stopping = False
        signal.signal(signal.SIGINT, lambda s, f: self.signal_handler(s, f))
        signal.signal(signal.SIGTERM, lambda s, f: self.signal_handler(s, f))

        os.makedirs(self.config.PATHS.RAW_DATA_DIR, exist_ok=True)
        os.makedirs(self.config.PATHS.MARKDOWN_DIR, exist_ok=True)
        os.makedirs(self.config.PATHS.DOCUMENT_DIR, exist_ok=True)
        os.makedirs(os.path.join(config.PATHS.RAW_DATA_DIR, "state"), exist_ok=True)

        # ** RESTORED ORIGINAL CSV COLUMNS **
        self.policies_df_path = os.path.join(self.config.PATHS.RAW_DATA_DIR, "crawled_policies_data.csv")
        self.csv_columns = ['url', 'file_path', 'include', 'found_links_count', 'definite_links', 'probable_links', 'timestamp'] # Added timestamp
        # Initialize CSV only if not resuming or if reset is forced
        if not config.CRAWLER.RESUME_CRAWL or config.CRAWLER.RESET_CRAWL:
            if config.CRAWLER.RESET_CRAWL and os.path.exists(self.policies_df_path):
                 try: os.remove(self.policies_df_path); self.logger.info(f"Removed CSV: {self.policies_df_path}")
                 except OSError as e: self.logger.error(f"Failed remove CSV on reset: {e}")
            if not os.path.exists(self.policies_df_path):
                 try: pd.DataFrame(columns=self.csv_columns).to_csv(self.policies_df_path, index=False); self.logger.info(f"Initialized CSV: {self.policies_df_path}")
                 except Exception as e: self.logger.error(f"Failed create CSV: {e}"); raise

        self._init_driver()

    def _init_driver(self):
        """Initialize the Selenium WebDriver. (Original logic)"""
        if self.driver: return
        self.logger.info("Initializing Chrome WebDriver...")
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized"); chrome_options.add_argument("--disable-notifications")
        try: self.driver = webdriver.Chrome(options=chrome_options); self.logger.info("WebDriver initialized successfully")
        except Exception as e: self.logger.error(f"Error initializing WebDriver: {str(e)}", exc_info=True); raise

    def signal_handler(self, signum, frame):
        """Handle termination signals. (Original logic)"""
        signal_name = signal.Signals(signum).name
        if not self.stopping:
            self.logger.info(f"Received {signal_name}. Saving state & shutting down..."); self.stopping = True
            self.save_state()
            if self.driver: self.logger.info("Closing browser...");
            try: self.driver.quit()
            except Exception as e: self.logger.error(f"Driver quit error on signal: {e}")
            self.logger.info("Crawler stopped gracefully. Resume with --resume.")
        else: self.logger.warning(f"{signal_name} received, already stopping.")
        sys.exit(0)

    def save_state(self):
        """Save the current crawler state. (Original logic)"""
        if self.current_url and isinstance(self.visited_urls, set) and isinstance(self.priority_queue, list):
            saved = self.state_manager.save_state(self.visited_urls, self.priority_queue, self.current_url, self.current_depth)
            if not saved: self.logger.error("Failed to save state!")
        else: self.logger.warning("Skipping state save: invalid state.")

    def load_state(self) -> bool:
        """Load previous crawler state if resuming. (Original logic, adjusted CSV check)"""
        if not self.config.CRAWLER.RESUME_CRAWL:
            self.logger.info("Resume mode disabled, starting fresh crawl"); self.state_manager.clear_state()
            if os.path.exists(self.policies_df_path):
                 try: os.remove(self.policies_df_path); self.logger.info("Removed CSV (resume disabled)."); pd.DataFrame(columns=self.csv_columns).to_csv(self.policies_df_path, index=False)
                 except OSError as e: self.logger.error(f"Failed remove/reinit CSV: {e}")
            return False
        state = self.state_manager.load_state()
        if not state: self.logger.info("No previous state to resume from"); return False
        try:
            self.visited_urls = state.get("visited_urls", set())
            self.priority_queue = state.get("priority_queue", []); heapq.heapify(self.priority_queue)
            self.current_url = state.get("current_url"); self.current_depth = state.get("current_depth", 0)
            self.logger.info(f"Resumed state: {len(self.visited_urls)} visited, {len(self.priority_queue)} in queue")
            if not os.path.exists(self.policies_df_path): self.logger.warning("State loaded but CSV missing. Initializing empty CSV."); pd.DataFrame(columns=self.csv_columns).to_csv(self.policies_df_path, index=False)
            return True
        except Exception as e:
             self.logger.error(f"Error applying loaded state: {e}. Starting fresh."); self.visited_urls=set(); self.priority_queue=[]; self.current_url=None; self.current_depth=0; self.state_manager.clear_state(); pd.DataFrame(columns=self.csv_columns).to_csv(self.policies_df_path, index=False); return False

    def start(self, initial_url: str = None):
        """Start the crawling process. (Original logic)"""
        try:
            start_url = initial_url if initial_url else self.config.CRAWLER.MAIN_URL
            if not self.driver: self._init_driver()
            if not self.driver: self.logger.critical("WebDriver init failed. Abort."); return
            self.logger.info(f"Opening initial URL: {start_url}"); self.driver.get(start_url)
            self.logger.info(">>> PAUSING: Log in/Navigate. Press Enter to start crawl..."); input(); self.logger.info(">>> Resuming...")
            resumed = self.load_state()
            if not resumed:
                current_start_url = self.driver.current_url; self.logger.info(f"Starting new crawl from: {current_start_url}")
                if self.is_allowed_url(current_start_url): heapq.heappush(self.priority_queue, (-100.0, current_start_url, 0))
                else: self.logger.warning(f"Initial URL {current_start_url} not allowed.")
            else: self.logger.info(f"Resuming crawl. Last URL: {self.current_url}")
            self.logger.info(f"Starting automated crawl loop (Max Depth: {self.config.CRAWLER.MAX_DEPTH})...")
            self.crawl_loop() # Renamed from crawl_automatically
        except Exception as e: self.logger.error(f"Fatal error: {e}", exc_info=True); self.save_state()
        finally:
            if not self.stopping: self.save_state()
            if self.driver: self.logger.info("Closing browser..."); self.driver.quit(); self.driver = None

    def crawl_loop(self): # Renamed from crawl_automatically
        """Run the automated crawling process using the priority queue."""
        # (Keep original loop structure)
        pages_processed = 0
        while self.priority_queue and not self.stopping:
            try:
                neg_priority, url, depth = heapq.heappop(self.priority_queue)
                priority = -neg_priority
                if url in self.visited_urls or not self.is_allowed_url(url): continue
                if depth > self.config.CRAWLER.MAX_DEPTH: continue

                self.current_url = url; self.current_depth = depth # Update state

                self.logger.info(f"\n{'='*80}\nProcessing [{pages_processed+1}] (Pri: {priority:.1f}, Depth: {depth}): {url}\n{'='*80}")
                # ** Call original process_url method **
                self.process_url(url, depth)
                pages_processed += 1

                if pages_processed % self.config.CRAWLER.SAVE_INTERVAL == 0:
                    self.save_state()
                    self.logger.info(f"Progress: {pages_processed} pages processed. Queue size: {len(self.priority_queue)}")

            except KeyboardInterrupt: self.logger.warning("KB Interrupt in loop."); self.signal_handler(signal.SIGINT, None); break
            except Exception as e: self.logger.error(f"Error processing URL {self.current_url}: {e}", exc_info=True); self.visited_urls.add(self.current_url); continue

        self.logger.info("Crawl loop finished.")
        # (Keep original finishing logic)
        if not self.stopping:
            if not self.priority_queue: self.logger.info("Crawler completed: Queue empty."); # Don't clear state automatically # self.state_manager.clear_state()
            else: self.logger.info(f"Crawler stopped: Max depth or other. {len(self.priority_queue)} URLs remain.")
            self.save_state()

    def is_allowed_url(self, url: str) -> bool:
        """Check if a URL is allowed for crawling. (Original logic)"""
        if not url or url.startswith(('#', 'javascript:', 'mailto:')): return False
        if url in self.visited_urls: return False # Check visited here
        try:
            pu = urllib.parse.urlparse(url)
            if pu.scheme not in ('http', 'https'): return False
            if not any(d in pu.netloc for d in self.config.CRAWLER.ALLOWED_DOMAINS): return False
        except ValueError: return False
        return True

    def is_document_url(self, url: str) -> bool:
        """Check if a URL points to a document. (Original logic)"""
        try:
            pu = urllib.parse.urlparse(url); p = pu.path.lower(); ext = os.path.splitext(p)[1]
            if ext and ext in self.config.CRAWLER.DOCUMENT_EXTENSIONS: return True
            if 'files-profile.medicine.yale.edu/documents/' in url or \
               re.match(r'https://files-profile\.medicine\.yale\.edu/documents/[a-f0-9-]+', url): return True
            dp = ['/documents/', '/attachments/', '/download/', '/dl/', '/docs/', '/files/', '/content/dam/']
            if any(pat in url.lower() for pat in dp): return True
        except Exception: return False
        return False

    def calculate_priority(self, url: str, link_text: str = "") -> float:
        """Calculate priority score for a URL. (Original logic)"""
        pu = urllib.parse.urlparse(url); p = pu.path.lower(); prio = 1.0
        for kw in self.config.CRAWLER.PRIORITY_KEYWORDS:
            if kw in p: prio += 5.0
            if f"/{kw}" in p or f"/{kw}." in p: prio += 3.0
        if link_text:
            lt = link_text.lower()
            for kw in self.config.CRAWLER.PRIORITY_KEYWORDS:
                 if kw in lt: prio += 4.0
        pd = p.count('/'); prio -= pd * 0.5
        if p.endswith('.pdf'): prio += 10.0
        elif p.endswith(('.doc', '.docx')): prio += 8.0
        if any(k in p for k in ['policy', 'policies', 'guideline', 'guidelines']): prio += 15.0
        if any(k in p for k in ['procedure', 'procedures', 'protocol', 'protocols']): prio += 12.0
        if any(k in p for k in ['search', 'login', 'contact']): prio -= 10.0
        return prio

    def extract_links(self, html_content: str, base_url: str) -> List[Tuple[str, str]]:
        """Extract links and their text from HTML content. (Original logic)"""
        pl = [];
        try:
             hl = re.findall(r'<a\s+[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_content, re.I | re.S)
             for lk, tx in hl:
                 lk = lk.strip(); tx = re.sub('<[^>]+>', '', tx).strip()
                 if not lk or lk.startswith(('#', 'javascript:', 'mailto:')): continue
                 al = urllib.parse.urljoin(base_url, lk)
                 aln = urllib.parse.urlunparse(urllib.parse.urlparse(al)._replace(fragment=''))
                 # Allow all valid links here; filtering happens before queueing
                 pl.append((aln, tx))
        except Exception as e: self.logger.error(f"Link extract error {base_url}: {e}")
        self.logger.info(f"Extracted {len(pl)} potential links from {base_url}")
        return pl

    def add_links_to_queue(self, links: List[Tuple[str, str]], depth: int):
        """Calculate priorities and add allowed, non-visited links to the priority queue."""
        # (Original logic)
        added_count = 0
        for url, link_text in links:
             # Check allowance and visited status BEFORE adding
            if self.is_allowed_url(url): # is_allowed_url checks visited set
                priority = self.calculate_priority(url, link_text)
                heapq.heappush(self.priority_queue, (-priority, url, depth))
                added_count += 1
                # Make info log less verbose or use debug
                # self.logger.info(f"Added to queue: {url} (Priority: {priority:.1f}, Depth: {depth})")
        if added_count > 0:
            self.logger.info(f"Added {added_count} new links to queue (Depth {depth}). Queue size: {len(self.priority_queue)}")


    # ** MODIFIED: process_url - main logic, incorporates saving/recording **
    def process_url(self, url: str, depth: int):
        """
        Process a URL: Get content, save raw file with timestamp, analyze content/links,
        record data to CSV, and queue relevant links.
        """
        # Mark as visited immediately to prevent re-queueing during processing
        self.visited_urls.add(url)
        self.logger.info(f"Processing URL: {url} at depth {depth}")

        markdown_content: Optional[str] = None
        all_links: List[Tuple[str, str]] = []
        saved_raw_path: Optional[str] = None
        saved_timestamp: Optional[str] = None

        # --- Get Content ---
        if self.is_document_url(url):
            self.logger.info(f"Processing as document: {url}")
            markdown_content, saved_raw_path, saved_timestamp = self._process_document_content(url)
        else:
            self.logger.info(f"Processing as webpage: {url}")
            markdown_content, all_links = self._process_webpage_content(url) # Gets links too

        # --- Save Raw File (if not already saved by PDF processor) & Record ---
        if markdown_content:
            # Determine filename and save if needed
            if not saved_raw_path: # Needs saving (webpage or non-OCR doc)
                now = datetime.datetime.now()
                saved_timestamp = now.strftime('%Y%m%d%H%M%S%f')
                filename = f"{saved_timestamp}.md"
                saved_raw_path = os.path.join(self.config.PATHS.MARKDOWN_DIR, filename)
                try:
                    header = f"# Source URL: {url}\n# Depth: {depth}\n# Timestamp: {saved_timestamp}\n\n---\n\n"
                    with open(saved_raw_path, 'w', encoding='utf-8') as f:
                        f.write(header + markdown_content)
                    self.logger.info(f"Saved Raw Markdown: {saved_raw_path}")
                except Exception as e:
                    self.logger.error(f"Failed to save raw MD {saved_raw_path}: {e}")
                    saved_raw_path = None # Mark as failed
            elif not saved_timestamp:
                 # Try to extract timestamp if path exists but timestamp wasn't returned
                 match = re.search(r"(\d{20})\.md$", os.path.basename(saved_raw_path))
                 if match: saved_timestamp = match.group(1)
                 else: self.logger.error(f"Could not determine timestamp for existing raw file: {saved_raw_path}")

            # Proceed only if we have a valid saved path and timestamp
            if saved_raw_path and saved_timestamp:
                # --- Analyze Content and Links (LLM Call) ---
                if self.config.LLM.OPENAI_API_KEY:
                     policy_result = analyze_content_for_policies(
                         content=markdown_content, url=url, links=all_links, config=self.config
                     )
                else:
                     self.logger.warning("OPENAI_API_KEY missing. Skipping LLM analysis.")
                     # Default result if LLM skipped
                     policy_result = {'include': False, 'content':'', 'definite_links': [], 'probable_links': []}
                     # Decide fallback link strategy if LLM is skipped
                     # Option 1: Queue all links found
                     # policy_result['definite_links'] = [link for link, text in all_links]
                     # Option 2: Queue none (safer)
                     # policy_result['definite_links'] = []

                # --- Record original CSV data ---
                relative_path = os.path.relpath(saved_raw_path, self.config.PATHS.MARKDOWN_DIR).replace(os.path.sep, '/')
                self.record_crawled_data_original(
                    url=url,
                    file_path=relative_path, # Relative path to timestamped file
                    include=policy_result.get('include', False),
                    found_links_count=len(all_links),
                    definite_links=policy_result.get('definite_links', []),
                    probable_links=policy_result.get('probable_links', []),
                    timestamp=saved_timestamp # Add timestamp column
                )

                # --- Queue Links based on LLM ---
                if depth < self.config.CRAWLER.MAX_DEPTH:
                    links_to_follow = []
                    is_root_url = (depth == 0) # Keep root fallback logic?
                    definite_links = policy_result.get('definite_links', [])
                    probable_links = policy_result.get('probable_links', [])

                    if is_root_url and not definite_links and not probable_links and all_links:
                        self.logger.warning("LLM found no policy links on root. Adding all (max 20).")
                        for link_url, link_text in all_links[:20]: links_to_follow.append((link_url, link_text))
                    else:
                        for link_url in definite_links:
                            link_text = next((text for l, text in all_links if l == link_url), "Definite Link")
                            links_to_follow.append((link_url, link_text))
                            self.logger.info(f"Queueing definite: {link_url}")
                        if not self.config.CRAWLER.FOLLOW_DEFINITE_LINKS_ONLY:
                            for link_url in probable_links:
                                link_text = next((text for l, text in all_links if l == link_url), "Probable Link")
                                links_to_follow.append((link_url, link_text))
                                self.logger.info(f"Queueing probable: {link_url}")

                    self.add_links_to_queue(links_to_follow, depth + 1)
            else:
                 self.logger.error(f"Failed to save or determine timestamp for raw content from {url}. Skipping record/queue.")
        else:
            self.logger.warning(f"No markdown content obtained for {url}. Skipping further processing.")


    # ** NEW HELPER **: Processes webpage content
    def _process_webpage_content(self, url: str) -> Tuple[Optional[str], List[Tuple[str, str]]]:
        """Gets MD content and links from a webpage."""
        markdown_content: Optional[str] = None
        links: List[Tuple[str, str]] = []
        if not self.driver: self.logger.error("WebDriver missing for webpage."); return None, []
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, self.config.CRAWLER.REQUEST_TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2) # Render pause
            html_content = self.driver.page_source
            if html_content:
                markdown_content = html_to_markdown(html_content)
                links = self.extract_links(html_content, url) # Extract links here
            else: self.logger.warning(f"Empty page source: {url}")
            self.logger.info(f"Webpage obtained: {url} (Links: {len(links)})")
        except Exception as e: self.logger.error(f"Selenium error {url}: {e}", exc_info=True)
        return markdown_content, links

    # ** NEW HELPER **: Processes document content
    def _process_document_content(self, url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Gets MD content, raw_path, raw_ts for documents."""
        markdown_content: Optional[str] = None
        raw_path: Optional[str] = None
        raw_ts: Optional[str] = None
        try:
            if url.lower().endswith('.pdf') or 'files-profile' in url:
                 raw_path, raw_ts = crawl_pdf_to_md(url, self.config.PATHS.MARKDOWN_DIR, self.config)
                 if raw_path and raw_ts and os.path.exists(raw_path):
                      with open(raw_path, 'r', encoding='utf-8') as f: markdown_content = f.read()
                      self.logger.info(f"Doc via OCR: {raw_path}")
                 else: self.logger.warning(f"OCR failed: {url}"); raw_path=None; raw_ts=None # Reset on failure
            else: # Other docs
                 tmp_dir = os.path.join(self.config.PATHS.DOCUMENT_DIR, f"tmp_{int(time.time()*1e6)}")
                 os.makedirs(tmp_dir, exist_ok=True)
                 dl_path = crawl_download_doc(url, tmp_dir, self.config)
                 if dl_path:
                      markdown_content = crawl_convert_to_md(dl_path, url, self.config)
                      self.logger.info(f"Doc via download/convert: {url}")
                      try: shutil.rmtree(tmp_dir)
                      except Exception as e: self.logger.warning(f"Cleanup failed {tmp_dir}: {e}")
                 else: self.logger.warning(f"Download/convert failed: {url}")
        except Exception as e: self.logger.error(f"Doc process error {url}: {e}", exc_info=True)
        return markdown_content, raw_path, raw_ts


    # ** MODIFIED: Use original columns + timestamp **
    def record_crawled_data_original(self, url: str, file_path: str, include: bool,
                                     found_links_count: int, definite_links: List[str],
                                     probable_links: List[str], timestamp: str):
        """Records data using the original CSV structure, adding timestamp."""
        try:
            # Ensure lists are dumped as JSON strings
            def_links_json = json.dumps(definite_links)
            prob_links_json = json.dumps(probable_links)

            new_data = {
                'url': [url],
                'file_path': [file_path], # Should be relative path to <timestamp>.md
                'include': [include],
                'found_links_count': [found_links_count],
                'definite_links': [def_links_json],
                'probable_links': [prob_links_json],
                'timestamp': [timestamp] # Add the timestamp
            }
            new_row_df = pd.DataFrame(new_data)

            file_exists = os.path.exists(self.policies_df_path)
            write_header = not file_exists or os.path.getsize(self.policies_df_path) == 0

            new_row_df.to_csv(self.policies_df_path, mode='a', header=write_header, index=False, lineterminator='\n')
            self.logger.debug(f"Recorded original CSV format for {url}")

        except Exception as e:
            self.logger.error(f"Error recording original CSV data for {url}: {e}", exc_info=True)

    # --- Removed original process_document, process_webpage, save_policy_content, record_policy_data ---
    # --- Logic is now primarily within process_url using helpers ---