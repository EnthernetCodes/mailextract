import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import time
import csv
import json
import os
import re

# ======= File Handling =======
def save_json(data, filename):
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            return json.load(file)
    return []

# ======= Accept Cookies Popups on Any Page (Skipped in BeautifulSoup) =======
def accept_cookies(session, url):
    pass  # Skipped in static parsing context

# ======= Extract Company Website from Europages Profile =======
def get_company_website(session, url):
    try:
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        button = soup.select_one("a.website-button")
        if button and button.get("href", "").startswith("http"):
            print(f"[INFO] Found official website: {button['href']}")
            return button['href']
        print("[INFO] No official site found.")
        return None
    except Exception as e:
        print(f"[ERROR] Exception while extracting website: {e}")
        return None

# ======= Extract Emails from the Official Website =======
def extract_emails_from_website(session, website_url):
    try:
        response = session.get(website_url, timeout=10)
        page_text = response.text
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", page_text)
        return list(set(emails))
    except Exception as e:
        print(f"[ERROR] Failed to extract emails from {website_url}: {e}")
        return []

# ======= Collect Europages Company Profile Links =======
def collect_company_links(session, page_urls):
    collected_links = load_json("collected_links.json")

    for url in tqdm(page_urls, desc="Collecting Europages Links", unit="page"):
        if url in collected_links:
            continue

        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a['href'] for a in soup.select("a[data-test='company-name']") if a.get("href", "").startswith("http")]
        collected_links.extend(links)
        collected_links = list(set(collected_links))
        save_json(collected_links, "collected_links.json")

    print(f"[✅] Total Europages profiles collected: {len(collected_links)}")
    return collected_links

# ======= Collect Official Websites from Europages Profiles =======
def collect_company_websites(session, europages_links):
    company_websites = load_json("company_websites.json")
    if not isinstance(company_websites, dict):
        company_websites = {}

    for link in tqdm(europages_links, desc="Extracting Official Websites", unit="company"):
        if link in company_websites:
            continue

        official_site = get_company_website(session, link)
        if official_site:
            company_websites[link] = official_site
            save_json(company_websites, "company_websites.json")

    print(f"[✅] Total company websites collected: {len(company_websites)}")
    return company_websites

# ======= Scrape Company Details from Official Websites =======
def scrape_company_details(session, company_websites, niche):
    scraped_data = load_json(f"{niche}_scraped_data.json")

    for europages_url, company_site in tqdm(company_websites.items(), desc="Scraping Company Details", unit="company"):
        if any(d["Website"] == company_site for d in scraped_data):
            continue

        print(f"[INFO] Visiting official site: {company_site}")
        emails = extract_emails_from_website(session, company_site)

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

# ======= Extract Emails and Company Names from CSV =======
def extract_email_and_company_from_csv(input_csv, output_csv):
    with open(input_csv, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        rows = []
        for row in reader:
            company_name = row["Website"].split("//")[-1].split("/")[0] if "Website" in row else ""
            email = row["Emails"].split(",")[0] if "Emails" in row and row["Emails"] else ""
            rows.append({"Company Name": company_name, "Email": email})

    with open(output_csv, "w", newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=["Company Name", "Email"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[✅] Extracted emails and company names saved to '{output_csv}'")

# ======= Main Execution =======
if __name__ == "__main__":
    session = requests.Session()
    niche = input("Enter the niche to search for: ").strip()
    max_pages = int(input("Enter the number of pages to scrape: ").strip())

    base_url = "https://www.europages.co.uk/en/search"
    page_urls = [f"{base_url}?cserpRedirect=1&q={niche}"] + [
        f"{base_url}/page/{page}?cserpRedirect=1&q={niche}" for page in range(2, max_pages + 1)
    ]

    europages_links = collect_company_links(session, page_urls)
    company_websites = collect_company_websites(session, europages_links)
    scraped_data = scrape_company_details(session, company_websites, niche)
    export_to_csv(scraped_data, f"{niche}_scraped_companies.csv")

    # Extract email and company name from machine_scraped_companies.csv
    extract_email_and_company_from_csv("machine_scraped_companies.csv", f"{niche}.csv")

    print("[✅] Scraping Complete!")
