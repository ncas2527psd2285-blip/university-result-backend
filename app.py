from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pandas as pd
import tempfile

app = Flask(__name__)
CORS(app)

RESULTS_URL = "https://egovernance.unom.ac.in/results/ugresult.asp"


def extract_results(driver):
    tables = driver.find_elements(By.TAG_NAME, "table")

    for table in tables:
        if "Subject Code" in table.text:
            rows = table.find_elements(By.TAG_NAME, "tr")
            results = {}

            for i in range(1, len(rows)):
                cols = rows[i].find_elements(By.TAG_NAME, "td")

                if len(cols) >= 4:
                    subject = cols[0].text.strip()
                    total = cols[3].text.strip()
                    results[subject] = total

            return results

    return {}


def get_student_results(driver, reg_no, dob):
    driver.get(RESULTS_URL)

    try:
        reg = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "regno"))
        )

        reg.clear()
        reg.send_keys(str(reg_no))

        pwd = driver.find_element(By.NAME, "pwd")
        pwd.clear()
        pwd.send_keys(str(dob))

        button = driver.find_element(By.XPATH, "//input[@value='Get Result']")
        button.click()

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        return extract_results(driver)

    except Exception as e:
        print("Error fetching:", reg_no, e)
        return {}


@app.route("/")
def home():
    return "Service is live"


@app.route("/process-results", methods=["POST"])
def process_results():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    file.save(temp_input.name)

    df = pd.read_excel(temp_input.name, dtype=str)
    df.columns = df.columns.str.strip()

    if (
        "Name" not in df.columns
        or "Register No" not in df.columns
        or "DOB" not in df.columns
    ):
        return jsonify(
            {"error": "Excel must contain Name, Register No and DOB"}
        ), 400

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)

    all_subjects = set()
    results_store = {}

    for _, row in df.iterrows():
        reg = row["Register No"]
        dob = row["DOB"]

        if pd.isna(reg) or pd.isna(dob):
            continue

        print("Fetching:", reg)

        res = get_student_results(driver, reg, dob)

        results_store[reg] = res
        all_subjects.update(res.keys())

    driver.quit()

    for subject in all_subjects:
        if subject not in df.columns:
            df[subject] = ""

    for i, row in df.iterrows():
        reg = row["Register No"]

        if reg not in results_store:
            continue

        for subject, mark in results_store[reg].items():
            df.loc[i, subject] = mark

    output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df.to_excel(output_file.name, index=False)

    fetched_count = sum(1 for res in results_store.values() if len(res) > 0)
    total_count = len(results_store)

    response = send_file(
        output_file.name,
        as_attachment=True,
        download_name="updated_results.xlsx",
    )

    response.headers["X-Total-Students"] = str(total_count)
    response.headers["X-Fetched-Students"] = str(fetched_count)

    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)