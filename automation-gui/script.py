import os
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

        with open(log_path, 'w') as log_file:
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    if len(cells) < 13:
                        continue

                    creative_name = cells[1].text.strip()
                    creative_id = cells[2].text.strip()
                    status = cells[3].text.strip().upper()
                    creative_type = cells[8].text.strip().lower()
                    placement_size = cells[9].text.strip().lower().replace(' ', '')
                    base_file_size_text = cells[12].text.strip().upper()

                    # Convert base file size to float KB
                    try:
                        size_value = float(base_file_size_text.replace("KB", "").strip())
                    except:
                        size_value = 0

                    print(f"[DEBUG] ID: {creative_id}, Status: {status}, Type: {creative_type}, Placement: {placement_size}, Name: {creative_name}, Size: {size_value}KB")

                    if status == 'QA':
                        log_msgs = []

                        # Test Case 1: Placement Size in Name
                        if placement_size in creative_name.replace(' ', '').lower():
                            log_msgs.append("✅ Placement size present")
                        else:
                            log_msgs.append(f"❌ Missing placement '{placement_size}'")

                        # Test Case 2: Valid Extension
                        if any(creative_name.lower().endswith(ext) for ext in all_extensions):
                            log_msgs.append("✅ File extension valid")
                        else:
                            log_msgs.append("❌ Missing or invalid file extension")

                        # Test Case 3: Type Check for image-based formats
                        if any(creative_name.lower().endswith(ext) for ext in image_extensions):
                            if creative_type == "altimage":
                                log_msgs.append("✅ Type is altimage for image format")
                            else:
                                log_msgs.append("❌ Type mismatch: should be 'altimage'")

                        # Test Case 4: Base File Size Limit
                        if size_value > 600:
                            log_msgs.append(f"❌ Base file size exceeds 600 KB ({size_value} KB)")
                        else:
                            log_msgs.append("✅ File size within limit")

                        result = f"ID: {creative_id} - " + ", ".join(log_msgs)
                        print("[LOG]", result)
                        log_file.write(result + '\n')

                except Exception as inner_e:
                    print("[WARN] Row error:", inner_e)

        print("[INFO] QA check completed. Results saved.")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to open URL: {e}")
        print(f"[ERROR] {e}")

def start_qa_check():
    url = url_entry.get().strip()
    if not url.startswith("http"):
        url = "https://" + url
    print(f"[DEBUG] Final URL: {url}")
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
