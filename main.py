from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
import csv
from datetime import datetime
from m import scrape_company_data, extract_emails

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///companies.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Database model
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))
    email = db.Column(db.String(256))
    website = db.Column(db.String(512))
    niche = db.Column(db.String(100))
    date_scraped = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Company {self.name}>'

with app.app_context():
    db.create_all()

# Helper to save to database

def save_to_db(data, niche):
    for entry in data:
        if entry.get("name") and entry.get("email"):
            existing = Company.query.filter_by(email=entry["email"]).first()
            if not existing:
                company = Company(
                    name=entry.get("name"),
                    email=entry.get("email"),
                    website=entry.get("website"),
                    niche=niche
                )
                db.session.add(company)
    db.session.commit()

# Helper to save to CSV

def save_to_csv(data, filename, fieldnames):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    return filepath

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        niche = request.form["niche"].strip()
        base_url = request.form["base_url"].strip()
        max_pages = int(request.form["max_pages"])

        session_data = scrape_company_data(base_url, max_pages)
        emails_data = extract_emails(session_data)

        scraped_csv = f"{niche}_scraped_companies.csv"
        emails_csv = f"{niche}_emails.csv"

        save_to_csv(session_data, scraped_csv, ["name", "website"])
        save_to_csv(emails_data, emails_csv, ["name", "email"])
        save_to_db(emails_data, niche)

        return redirect(url_for("results", 
                                niche=niche,
                                scraped_file=scraped_csv,
                                email_file=emails_csv))
    return render_template("index.html")

@app.route("/results/<niche>")
def results(niche):
    scraped_file = request.args.get("scraped_file")
    email_file = request.args.get("email_file")
    return render_template("results.html", 
                           scraped_file=scraped_file, 
                           email_file=email_file, 
                           niche=niche)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route("/companies")
def view_companies():
    companies = Company.query.order_by(Company.date_scraped.desc()).all()
    return render_template("companies.html", companies=companies)

if __name__ == "__main__":
    app.run(debug=True)
