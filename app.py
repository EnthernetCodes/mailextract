from flask import Flask, request, render_template, redirect, url_for
import csv
from m import (
    collect_company_links,
    collect_company_websites,
    scrape_company_details,
    export_to_csv,
    extract_email_and_company_from_csv,
    save_json
)
import requests

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        niche = request.form["niche"]
        max_pages = int(request.form["max_pages"])

        # Setup page URLs
        base_url = "https://www.europages.co.uk/en/search"
        page_urls = [f"{base_url}?cserpRedirect=1&q={niche}"] + [
            f"{base_url}/page/{page}?cserpRedirect=1&q={niche}" for page in range(2, max_pages + 1)
        ]

        # Start scraping process using requests + BeautifulSoup
        session = requests.Session()
        europages_links = collect_company_links(session, page_urls)
        company_websites = collect_company_websites(session, europages_links)
        scraped_data = scrape_company_details(session, company_websites, niche)

        # Save main scraped data and emails
        csv_file = f"{niche}_scraped_companies.csv"
        export_to_csv(scraped_data, csv_file)
        extract_email_and_company_from_csv(csv_file, f"{niche}_emails.csv")

        return redirect(url_for("results", niche=niche))

    return render_template("index.html")

@app.route("/results/<niche>")
def results(niche):
    csv_file = f"{niche}_scraped_companies.csv"
    email_file = f"{niche}_emails.csv"

    # Read results from CSV
    results_data = []
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            results_data = list(reader)
    except FileNotFoundError:
        results_data = []

    progress = {
        "niche": niche,
        "csv_file": csv_file,
        "email_file": email_file,
    }
    return render_template("results.html", results_data=results_data, progress=progress)

if __name__ == "__main__":
    app.run(debug=True)
