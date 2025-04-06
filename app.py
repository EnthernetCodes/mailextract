from flask import Flask, request, render_template, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import os
import json
import csv
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scraper.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    niche = db.Column(db.String(100))
    europages_profile = db.Column(db.String(300))
    website = db.Column(db.String(300))
    emails = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ScrapeProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    niche = db.Column(db.String(100))
    current_stage = db.Column(db.String(100))
    progress_detail = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

def update_progress(niche, stage, detail):
    progress = ScrapeProgress.query.filter_by(niche=niche).first()
    if not progress:
        progress = ScrapeProgress(niche=niche, current_stage=stage, progress_detail=detail)
        db.session.add(progress)
    else:
        progress.current_stage = stage
        progress.progress_detail = detail
        progress.updated_at = datetime.utcnow()
    db.session.commit()

def save_company(niche, profile, website, emails):
    entry = Company(niche=niche, europages_profile=profile, website=website, emails=", ".join(emails))
    db.session.add(entry)
    db.session.commit()

def get_company_website(session, url):
    try:
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        button = soup.select_one("a.website-button")
        if button and button.get("href", "").startswith("http"):
            return button['href']
        return None
    except:
        return None

def extract_emails_from_website(session, website_url):
    try:
        response = session.get(website_url, timeout=10)
        page_text = response.text
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}", page_text)
        return list(set(emails))
    except:
        return []

def collect_company_links(session, page_urls):
    links = []
    for url in page_urls:
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        links += [a['href'] for a in soup.select("a[data-test='company-name']") if a.get("href", "").startswith("http")]
    return list(set(links))

def run_scraper(niche, pages):
    session = requests.Session()
    base_url = "https://www.europages.co.uk/en/search"
    page_urls = [f"{base_url}?cserpRedirect=1&q={niche}"] + [
        f"{base_url}/page/{page}?cserpRedirect=1&q={niche}" for page in range(2, pages + 1)
    ]
    update_progress(niche, "Collecting Links", f"Scraping {pages} pages")
    links = collect_company_links(session, page_urls)
    update_progress(niche, "Extracting Websites", f"{len(links)} companies found")

    for link in links:
        website = get_company_website(session, link)
        if website:
            emails = extract_emails_from_website(session, website)
            if emails:
                save_company(niche, link, website, emails)

    update_progress(niche, "Completed", f"Scraping complete. {len(links)} processed")

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        niche = request.form['niche']
        pages = int(request.form['pages'])
        run_scraper(niche, pages)
        return redirect(url_for('status', niche=niche))
    return render_template("index.html")

@app.route("/status/<niche>")
def status(niche):
    progress = ScrapeProgress.query.filter_by(niche=niche).first()
    companies = Company.query.filter_by(niche=niche).all()
    return render_template("status.html", progress=progress, companies=companies)

@app.route("/download/<niche>")
def download(niche):
    filename = os.path.join(app.config['UPLOAD_FOLDER'], f"{niche}_results.csv")
    companies = Company.query.filter_by(niche=niche).all()
    with open(filename, "w", newline='', encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Company Name", "Email", "Website", "Europages Profile"])
        for c in companies:
            name = c.website.split('//')[-1].split('/')[0]
            email = c.emails.split(',')[0]
            writer.writerow([name, email, c.website, c.europages_profile])
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
