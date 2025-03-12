import os
import time
import logging
import random
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from fake_useragent import UserAgent
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from colorama import init, Fore, Style
from datetime import datetime
import json
from typing import Dict, List, Optional

# Initialize colorama for cross-platform colored output
init()

# Project Banner
PROJECT_NAME = "DarkScraper v2.1"
BANNER = f"""
{Fore.GREEN}============================================================{Style.RESET_ALL}
{Fore.RED}      {PROJECT_NAME} - Elite Facebook Data Harvester      {Style.RESET_ALL}
{Fore.GREEN}============================================================{Style.RESET_ALL}
{Fore.CYAN} Coded by: Shiboshree Roy | Date: {datetime.now().strftime('%Y-%m-%d')} {Style.RESET_ALL}
{Fore.YELLOW} Stealth Mode: ON | Target: Facebook Profiles {Style.RESET_ALL}
{Fore.GREEN}============================================================{Style.RESET_ALL}
"""

# Configure logging with colored output
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }
    def format(self, record):
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"

logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()
for handler in logger.handlers:
    handler.setFormatter(ColoredFormatter())

# Constants
OUTPUT_DIR = "dark_output"
MAX_RETRIES = 3
RATE_LIMIT_DELAY = lambda: random.uniform(3, 8)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Proxy configuration (replace with real proxy service credentials)
PROXY_LIST = [
    {"host": "proxy1.example.com", "port": 8080, "user": "user1", "pass": "pass1"},
    {"host": "proxy2.example.com", "port": 8080, "user": "user2", "pass": "pass2"}
]

# Function to initialize Selenium WebDriver with stealth
def init_driver(use_proxy: bool = False, proxy: Optional[Dict] = None) -> Optional[webdriver.Chrome]:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")

    ua = UserAgent()
    chrome_options.add_argument(f"user-agent={ua.random}")

    if use_proxy and proxy:
        proxy_str = f"http://{proxy['user']}:{proxy['pass']}@{proxy['host']}:{proxy['port']}"
        chrome_options.add_argument(f"--proxy-server={proxy_str}")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    try:
        driver = webdriver.Chrome(service=Service(), options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logging.info("WebDriver initialized successfully.")
        return driver
    except WebDriverException as e:
        logging.error(f"WebDriver initialization failed: {e}")
        return None

# Function to handle CAPTCHA
def handle_captcha(driver: webdriver.Chrome) -> bool:
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'CAPTCHA')]"))
        )
        logging.warning("CAPTCHA detected! Attempting bypass...")
        time.sleep(10)  # Placeholder for solver
        return True
    except TimeoutException:
        return False

# Function to extract Facebook profile info
def extract_facebook_info(driver: webdriver.Chrome, profile_url: str, retries: int = MAX_RETRIES) -> Dict:
    for attempt in range(retries):
        try:
            driver.get(profile_url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(RATE_LIMIT_DELAY())

            if handle_captcha(driver):
                logging.info("CAPTCHA bypassed, retrying extraction.")
                continue

            soup = BeautifulSoup(driver.page_source, "html.parser")
            info = {
                "Name": "Not Found",
                "Birthday": "Not Found",
                "Email": "Not Found",
                "Phone": "Not Found",
                "Gender": "Not Found",
                "Profile_URL": profile_url,
                "Friends_Count": "Not Found",
                "Posts_Count": "Not Found",
                "Last_Updated": datetime.now().isoformat(),
                "Status": "Success"
            }

            try:
                info["Name"] = soup.select_one("#fb-timeline-cover-name a").get_text(strip=True)
            except AttributeError:
                pass

            try:
                about = soup.select_one(".about-section")
                if about:
                    info["Birthday"] = about.find(text="Birthday").find_next().get_text(strip=True)
            except AttributeError:
                pass

            try:
                info["Email"] = soup.select_one(".email-field") or "Not Found"
            except AttributeError:
                pass

            try:
                info["Phone"] = soup.select_one(".phone-field") or "Not Found"
            except AttributeError:
                pass

            try:
                info["Gender"] = soup.select_one(".gender-field") or "Not Found"
            except AttributeError:
                pass

            try:
                friends = soup.select_one(".friends-count").get_text(strip=True)
                info["Friends_Count"] = friends
            except AttributeError:
                pass

            try:
                posts = len(soup.select(".user-post"))
                info["Posts_Count"] = str(posts)
            except AttributeError:
                pass

            return info

        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{retries} failed for {profile_url}: {e}")
            time.sleep(RATE_LIMIT_DELAY() * (attempt + 1))
            if attempt == retries - 1:
                return {"Profile_URL": profile_url, "Status": "Failed", "Error": str(e)}

# Function to enrich data
def enrich_data(info: Dict) -> Dict:
    if info["Email"] != "Not Found":
        try:
            response = requests.get(f"https://api.hunter.io/v2/email-finder?email={info['Email']}", timeout=5)
            if response.status_code == 200:
                enriched = response.json()
                info["Location"] = enriched.get("data", {}).get("country", "Not Found")
        except requests.RequestException as e:
            logging.warning(f"Data enrichment failed: {e}")
    return info

# Function to save data
def save_data(data: List[Dict], filename_base: str) -> None:
    df = pd.DataFrame(data)
    csv_path = os.path.join(OUTPUT_DIR, f"{filename_base}.csv")
    json_path = os.path.join(OUTPUT_DIR, f"{filename_base}.json")
    df.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(data, f, indent=4)
    logging.info(f"Data harvested to {csv_path} and {json_path}")

# Worker function for concurrent scraping
def process_profile(profile_url: str, use_proxy: bool) -> Dict:
    proxy = random.choice(PROXY_LIST) if use_proxy else None
    driver = init_driver(use_proxy=use_proxy, proxy=proxy)
    if not driver:
        return {"Profile_URL": profile_url, "Status": "Failed", "Error": "Driver init failed"}
    
    info = extract_facebook_info(driver, profile_url)
    driver.quit()
    if info["Status"] == "Success":
        info = enrich_data(info)
    return info

# Function to get profile URLs from user input
def get_profile_urls_from_user() -> List[str]:
    print(f"{Fore.YELLOW}Enter Facebook profile URLs (one per line). Type 'done' when finished:{Style.RESET_ALL}")
    urls = []
    while True:
        url = input(f"{Fore.CYAN}>> {Style.RESET_ALL}").strip()
        if url.lower() == "done":
            if not urls:
                print(f"{Fore.RED}No URLs provided. Aborting mission.{Style.RESET_ALL}")
                exit(1)
            break
        if url.startswith("https://www.facebook.com/"):
            urls.append(url)
            print(f"{Fore.GREEN}Added: {url}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Invalid URL. Must start with 'https://www.facebook.com/'. Try again.{Style.RESET_ALL}")
    return urls

# Main function
def main(use_proxy: bool = False, max_workers: int = 4) -> None:
    print(BANNER)
    profile_urls = get_profile_urls_from_user()
    logging.info(f"Initializing {PROJECT_NAME} with {len(profile_urls)} targets.")
    
    all_data = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(process_profile, url, use_proxy): url for url in profile_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                all_data.append(data)
                logging.info(f"Target {url} processed.")
            except Exception as e:
                logging.error(f"Critical failure for {url}: {e}")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_data(all_data, f"dark_profiles_{timestamp}")
    logging.info(f"{PROJECT_NAME} mission completed. Data secured.")

# Entry point
if __name__ == "__main__":
    main(use_proxy=True, max_workers=4)