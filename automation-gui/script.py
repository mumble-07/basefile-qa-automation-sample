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

def open_url_with_selenium(url):
    try:
        print("[DEBUG] Starting open_url_with_selenium")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        chromedriver_path = os.path.abspath(os.path.join(current_dir, '..', 'chromedriver-mac-arm64', 'chromedriver'))
        print(f"[DEBUG] ChromeDriver path: {chromedriver_path}")

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
        print("[DEBUG] Chrome launched, loading URL...")

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.creatives-table"))
        )
        time.sleep(2)

        rows = driver.find_elements(By.CSS_SELECTOR, "table.creatives-table tbody tr")
        print(f"[DEBUG] Found {len(rows)} creative rows")

        image_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        all_extensions = image_extensions + ['.zip', '.svg', '.mp4', '.webm']
        log_path = os.path.join(current_dir, 'qa_check_results.txt')
        print(f"[INFO] Log file path: {log_path}")

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

                    if placement_size == "1x1":
                        log_msgs.append("✅ AUTO-APPROVED: 1x1 placement detected, skipping other checks")
                        result = f"ID: {creative_id} - " + ", ".join(log_msgs)
                        log_file.write(result + '\n')
                        continue

                    if status == 'QA':
                        if placement_size in creative_name.replace(' ', '').lower():
                            log_msgs.append("✅ Placement size present")
                        else:
                            log_msgs.append(f"❌ Missing placement '{placement_size}'")

                        if any(creative_name.lower().endswith(ext) for ext in all_extensions):
                            log_msgs.append("✅ File extension valid")
                        else:
                            log_msgs.append("❌ Missing or invalid file extension")

                        if any(creative_name.lower().endswith(ext) for ext in image_extensions):
                            if creative_type.lower() == "altimage":
                                log_msgs.append("✅ Type is altimage for image format")
                            else:
                                log_msgs.append("❌ Type mismatch: should be 'altimage'")

                        if size_value > 600:
                            log_msgs.append(f"❌ Base file size exceeds 600 KB ({size_value} KB)")
                        else:
                            log_msgs.append("✅ File size within limit")

                        if creative_name.lower().endswith(".zip"):
                            if creative_type in ["HTML_Standard", "HTML_onpage"]:
                                log_msgs.append("✅ Correct type for .zip file")
                            else:
                                log_msgs.append("❌ .zip file must be HTML_Standard or HTML_onpage")

                        if creative_name == file_name:
                            log_msgs.append("✅ Creative name matches file name")
                        else:
                            log_msgs.append("❌ Creative name does not match file name")

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
                                log_msgs.append("❌ ClickTag not detected")

                            logs = driver.get_log("browser")
                            filtered_errors = [
                                entry for entry in logs
                                if entry['level'] == 'SEVERE' and creative_domain in entry['message']
                            ]
                            if filtered_errors:
                                log_msgs.append("❌ Console error detected (from creative)")
                                for entry in filtered_errors:
                                    msg = entry['message'].replace('\n', ' ').replace('\r', '')
                                    log_file.write(f"[Console:{creative_id}] {entry['level']}: {msg}\n")
                            else:
                                log_msgs.append("✅ No console errors")

                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                        except Exception as preview_e:
                            log_msgs.append("⚠️ ClickTag/Console check failed")

                    result = f"ID: {creative_id} - " + ", ".join(log_msgs)
                    log_file.write(result + '\n')

                except Exception as inner_e:
                    print("[WARN] Row error:", inner_e)

        print("[INFO] QA check completed. Results saved.")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to open URL: {e}")

def start_qa_check():
    url = url_entry.get().strip()
    if not url.startswith("http"):
        url = "https://" + url
    threading.Thread(target=open_url_with_selenium, args=(url,)).start()

# GUI
root = tk.Tk()
root.title("QA Link Checker")
root.geometry("400x150")
root.resizable(False, False)

label = tk.Label(root, text="Enter URL for QA Check:")
label.pack(pady=10)

url_entry = tk.Entry(root, width=50)
url_entry.pack()

qa_button = tk.Button(root, text="QA CHECK", command=start_qa_check)
qa_button.pack(pady=20)

root.mainloop()
