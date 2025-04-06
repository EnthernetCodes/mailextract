import csv
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
    niche = input("Enter the niche to search for: ").strip()
    # Extract email and company name from machine_scraped_companies.csv
    extract_email_and_company_from_csv("machine_scraped_companies.csv", f"{niche}.csv")

    print("[✅] Scraping Complete!")
