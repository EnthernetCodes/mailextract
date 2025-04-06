from flask import Flask, request, render_template, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import os
import csv
from m import * #extract_company_emails  # Import scraping logic

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scrape.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# === DATABASE MODELS ===

class ScrapeResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    niche = db.Column(db.String(100))
    company_name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    website = db.Column(db.String(300))
    europages_profile = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

class ScrapeProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    niche = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(50))
    message = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))


# === HELPER TO UPDATE PROGRESS ===

def set_progress(niche, status, message):
    progress = ScrapeProgress.query.filter_by(niche=niche).first()
    if not progress:
        progress = ScrapeProgress(niche=niche)
        db.session.add(progress)
    progress.status = status
    progress.message = message
    progress.updated_at = datetime.now(timezone.utc)
    db.session.commit()


# === ROUTES ===

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        niche = request.form['niche'].strip()
        if niche:
            set_progress(niche, "pending", "Scraping started...")
            return redirect(url_for('scrape_status', niche=niche))
    return render_template('index.html')


@app.route('/status/<niche>')
def scrape_status(niche):
    progress = ScrapeProgress.query.filter_by(niche=niche).first()
    results = ScrapeResult.query.filter_by(niche=niche).all()

    return render_template('status.html', 
                           progress=progress, 
                           results=results, 
                           niche=niche)


@app.route('/scrape/<niche>')
def scrape_niche(niche):
    set_progress(niche, "processing", "Scraping in progress...")

    try:
        data = extract_company_emails(niche, lambda status, msg: set_progress(niche, status, msg))
        for row in data:
            result = ScrapeResult(
                niche=niche,
                company_name=row.get('Company Name'),
                email=row.get('Email'),
                website=row.get('Website'),
                europages_profile=row.get('Europages Profile')
            )
            db.session.add(result)

        set_progress(niche, "completed", f"Scraping complete. {len(data)} processed")
        db.session.commit()

    except Exception as e:
        set_progress(niche, "failed", f"Error: {str(e)}")

    return redirect(url_for('scrape_status', niche=niche))


@app.route('/download/<niche>')
def download_results(niche):
    results = ScrapeResult.query.filter_by(niche=niche).all()
    filename = f"{niche}_results.csv"
    filepath = os.path.join("downloads", filename)
    os.makedirs("downloads", exist_ok=True)

    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Company Name", "Email", "Website", "Europages Profile"])
        for r in results:
            writer.writerow([r.company_name, r.email, r.website, r.europages_profile])

    return send_file(filepath, as_attachment=True)


# === INIT ===

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
