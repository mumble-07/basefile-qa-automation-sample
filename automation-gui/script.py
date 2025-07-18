import os
import urllib.parse
import tkinter as tk
import threading
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime

def open_url_with_selenium(url):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        results_dir = os.path.join(current_dir, 'results_log')
        os.makedirs(results_dir, exist_ok=True)

        chromedriver_path = os.path.abspath(os.path.join(current_dir, '..', 'chromedriver-mac-arm64', 'chromedriver'))

        chrome_options = Options()
        chrome_options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--start-maximized")
        chrome_options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.creatives-table"))
        )
        time.sleep(2)

        rows = driver.find_elements(By.CSS_SELECTOR, "table.creatives-table tbody tr")
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_path = os.path.join(results_dir, f'qa_check_results_{timestamp}.txt')

        image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        all_extensions = image_extensions + ['.zip', '.svg', '.mp4', '.webm']

        summary_errors = {}

        with open(log_path, 'w', encoding='utf-8') as log_file:
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    if len(cells) < 18:
                        continue

                    creative_name = cells[1].text.strip()
                    creative_id = cells[2].text.strip()
                    status = cells[3].text.strip().upper()
                    creative_type = cells[8].text.strip()
                    placement_size_raw = cells[9].text.strip()
                    placement_size = placement_size_raw.lower().replace(' ', '')
                    base_file_size_text = cells[12].text.strip().upper()
                    file_name = cells[17].text.strip()

                    try:
                        size_value = float(base_file_size_text.replace("KB", "").strip())
                    except:
                        size_value = 0

                    log_msgs = []
                    errors = []

                    if placement_size == "1x1":
                        msg = "✅ AUTO-APPROVED: 1x1 placement detected, skipping other checks"
                        log_msgs.append(msg)
                        result = f"ID: {creative_id} - " + msg
                        log_file.write(result + '\n')
                        continue

                    if status == 'QA':
                        if placement_size in creative_name.replace(' ', '').lower():
                            log_msgs.append("✅ Placement size present")
                        else:
                            msg = f"❌ Missing placement '{placement_size}'"
                            log_msgs.append(msg)
                            errors.append(msg)

                        if any(creative_name.lower().endswith(ext) for ext in all_extensions):
                            log_msgs.append("✅ File extension valid")
                        else:
                            msg = "❌ Missing or invalid file extension"
                            log_msgs.append(msg)
                            errors.append(msg)

                        if any(creative_name.lower().endswith(ext) for ext in image_extensions):
                            if creative_type.lower() == "altimage":
                                log_msgs.append("✅ Type is altimage for image format")
                            else:
                                msg = "❌ Type mismatch: should be 'altimage'"
                                log_msgs.append(msg)
                                errors.append(msg)

                        if size_value > 600:
                            msg = f"❌ Base file size exceeds 600 KB ({size_value} KB)"
                            log_msgs.append(msg)
                            errors.append(msg)
                        else:
                            log_msgs.append("✅ File size within limit")

                        if creative_name.lower().endswith(".zip"):
                            if creative_type in ["HTML_Standard", "HTML_onpage"]:
                                log_msgs.append("✅ Correct type for .zip file")
                            else:
                                msg = "❌ .zip file must be HTML_Standard or HTML_onpage"
                                log_msgs.append(msg)
                                errors.append(msg)

                        if creative_name == file_name:
                            log_msgs.append("✅ Creative name matches file name")
                        else:
                            msg = "❌ Creative name does not match file name"
                            log_msgs.append(msg)
                            errors.append(msg)

                        try:
                            anchor = cells[1].find_element(By.TAG_NAME, 'a')
                            href = anchor.get_attribute("href")
                            creative_domain = urllib.parse.urlparse(href).netloc
                            driver.execute_script("window.open(arguments[0]);", href)
                            driver.switch_to.window(driver.window_handles[-1])
                            time.sleep(3)

                            if "clicktag" in driver.page_source.lower():
                                log_msgs.append("✅ ClickTag found in preview")
                            else:
                                msg = "❌ ClickTag not detected"
                                log_msgs.append(msg)
                                errors.append(msg)

                            logs = driver.get_log("browser")
                            filtered_errors = [
                                entry for entry in logs
                                if entry['level'] == 'SEVERE' and creative_domain in entry['message']
                            ]
                            if filtered_errors:
                                msg = "❌ Console error detected (from creative)"
                                log_msgs.append(msg)
                                errors.append(msg)
                                for entry in filtered_errors:
                                    clean_msg = entry['message'].replace('\n', ' ').replace('\r', '')
                                    log_file.write(f"[Console:{creative_id}] {entry['level']}: {clean_msg}\n")
                            else:
                                log_msgs.append("✅ No console errors")

                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        except Exception as preview_e:
                            msg = "⚠️ ClickTag/Console check failed"
                            log_msgs.append(msg)
                            errors.append(msg)

                    # ✅ Final UI update: if QA and no errors, convert to Approved visually
                    if status == "QA" and not errors:
                        try:
                            status_cell = cells[3]
                            driver.execute_script("""
                                arguments[0].innerHTML = '<span class="approved-pill">Approved</span>';
                            """, status_cell)
                            log_msgs.append("✅ All test cases passed – status changed to Approved in UI")
                        except Exception as dom_e:
                            log_msgs.append("⚠️ Failed to change status to Approved in DOM")

                    result = f"ID: {creative_id} - " + ", ".join(log_msgs)
                    log_file.write(result + '\n')
                    if errors:
                        summary_errors[creative_id] = errors

                except Exception as inner_e:
                    print("[WARN] Row error:", inner_e)

            if summary_errors:
                log_file.write("\n\n=== SUMMARY OF FAILED CHECKS ===\n")
                for cid, errs in summary_errors.items():
                    log_file.write(f"ID: {cid}\n")
                    for e in errs:
                        log_file.write(f"  - {e}\n")
                    log_file.write("\n")

        log_label.config(text=f"✅ QA check completed! Log saved to: {log_path}", fg="green")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to open URL: {e}")
        log_label.config(text="❌ Error during QA check", fg="red")

def start_qa_check():
    url = url_entry.get().strip()
    if not url.startswith("http"):
        url = "https://" + url
    log_label.config(text="🔄 Running QA check...", fg="blue")
    threading.Thread(target=open_url_with_selenium, args=(url,)).start()

# GUI Setup
root = tk.Tk()
root.title("QA Link Checker")
root.geometry("460x180")
root.resizable(False, False)

label = tk.Label(root, text="Enter URL for QA Check:", font=("Arial", 11))
label.pack(pady=(10, 0))

url_entry = tk.Entry(root, width=60, font=("Arial", 10))
url_entry.pack(pady=5)

qa_button = tk.Button(root, text="QA CHECK", command=start_qa_check, font=("Arial", 10, "bold"), bg="#123F72", fg="black", padx=10, pady=2)
qa_button.pack(pady=10)

log_label = tk.Label(root, text="", font=("Arial", 10))
log_label.pack(pady=(5, 0))

root.mainloop()
