from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from tqdm import tqdm
import time
import csv
import json
import os
import re

# ======= Initialize Browser =======
def init_browser():
    service = Service(ChromeDriverManager().install())
    chrome_options = Options()
    
    show_browser = input("Do you want to open the browser and watch it work? (yes/no): ").strip().lower()
    if show_browser == "no":
        chrome_options.add_argument("--headless")  # Run in headless mode

    browser = webdriver.Chrome(service=service, options=chrome_options)
    browser.implicitly_wait(10)
    print("[INFO] Browser initialized.")
    return browser

# ======= File Handling =======
def save_json(data, filename):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return []

# ======= Accept Cookies Popups on Any Page =======
def accept_cookies(browser):
    try:
        cookie_buttons = WebDriverWait(browser, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'accept')]"))
        )
        for button in cookie_buttons:
            try:
                button.click()
                print("[INFO] Cookie popup accepted.")
                time.sleep(2)
            except:
                continue
    except TimeoutException:
        print("[INFO] No cookie popup found.")

# ======= Extract Company Website from Europages Profile =======
def get_company_website(browser):
    try:
        visit_site_button = WebDriverWait(browser, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.website-button"))
        )
        website_url = visit_site_button.get_attribute("href")

        if website_url and website_url.startswith("http"):
            print(f"[INFO] Found official website: {website_url}")
            return website_url
    except TimeoutException:
        print("[INFO] No official site found.")
        return None
    return None

# ======= Extract Emails from the Official Website =======
def extract_emails_from_website(browser, website_url):
    try:
        browser.get(website_url)
        accept_cookies(browser)  # Accept cookies on company website
        time.sleep(3)
        
        # Extract emails using regex
        page_text = browser.page_source
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", page_text)
        
        return list(set(emails))  # Remove duplicates
    except Exception as e:
        print(f"[ERROR] Failed to extract emails from {website_url}: {e}")
        return []

# ======= Collect Europages Company Profile Links =======
def collect_company_links(browser, page_urls):
    """ Collect Europages profile links & store them. """
    collected_links = load_json("collected_links.json")

    for url in tqdm(page_urls, desc="Collecting Europages Links", unit="page"):
        if url in collected_links:
            continue

        browser.get(url)
        accept_cookies(browser)  # Accept cookies on each Europages page
        time.sleep(3)
        
        # Extract company profile links
        links = [link.get_attribute("href") for link in browser.find_elements(By.CSS_SELECTOR, "a[data-test='company-name']")]
        links = [href for href in links if href and href.startswith("http")]
        
        collected_links.extend(links)
        save_json(collected_links, "collected_links.json")

    print(f"[✅] Total Europages profiles collected: {len(collected_links)}")
    return collected_links

# ======= Collect Official Websites from Europages Profiles =======
def collect_company_websites(browser, europages_links):
    """ Visit each Europages profile & extract official website links. """
    company_websites = load_json("company_websites.json")
    
    # Fix: Ensure company_websites is a dictionary
    if not isinstance(company_websites, dict):
        company_websites = {}

    for link in tqdm(europages_links, desc="Extracting Official Websites", unit="company"):
        if link in company_websites:  # Skip already processed profiles
            continue

        browser.get(link)
        accept_cookies(browser)  # Accept cookies on company profile page
        time.sleep(3)

        official_site = get_company_website(browser)
        if official_site:
            company_websites[link] = official_site  # Store as {europages_link: official_site}
            save_json(company_websites, "company_websites.json")

    print(f"[✅] Total company websites collected: {len(company_websites)}")
    return company_websites

# ======= Scrape Company Details from Official Websites =======
def scrape_company_details(browser, company_websites, niche):
    scraped_data = load_json(f"{niche}_scraped_data.json")

    for europages_url, company_site in tqdm(company_websites.items(), desc="Scraping Company Details", unit="company"):
        if any(d["Website"] == company_site for d in scraped_data):
            continue  # Skip if already scraped

        print(f"[INFO] Visiting official site: {company_site}")
        emails = extract_emails_from_website(browser, company_site)

        if emails:
            scraped_data.append({
                "Europages Profile": europages_url,
                "Website": company_site,
                "Emails": emails
            })
            save_json(scraped_data, f"{niche}_scraped_data.json")

    return scraped_data

# ======= Export to CSV =======
def export_to_csv(data, filename):
    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Europages Profile", "Website", "Emails"])
        writer.writeheader()
        for entry in data:
            writer.writerow({
                "Europages Profile": entry["Europages Profile"],
                "Website": entry["Website"],
                "Emails": ", ".join(entry["Emails"])
            })
    print(f"[✅] Data exported to '{filename}'")

# ======= Main Execution =======
if __name__ == "__main__":
    browser = init_browser()
    
    niche = input("Enter the niche to search for: ").strip()
    max_pages = int(input("Enter the number of pages to scrape: ").strip())
    
    base_url = "https://www.europages.co.uk/en/search"
    page_urls = [f"{base_url}?cserpRedirect=1&q={niche}"] + [
        f"{base_url}/page/{page}?cserpRedirect=1&q={niche}" for page in range(2, max_pages + 1)
    ]
    
    # Step 1: Collect Europages Company Profile Links
    europages_links = collect_company_links(browser, page_urls)
    
    # Step 2: Collect Official Websites
    company_websites = collect_company_websites(browser, europages_links)
    
    # Step 3: Scrape Company Details
    scraped_data = scrape_company_details(browser, company_websites, niche)
    
    # Step 4: Export Data to CSV
    export_to_csv(scraped_data, f"{niche}_scraped_companies.csv")
    
    browser.quit()
    print("[✅] Scraping Complete!")
