import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
import threading
import traceback
import time
import pyautogui  # For real zoom

# --- Global Driver ---
driver = None

# --- Start / Restart Driver ---
def start_driver():
    global driver
    if driver:
        try:
            driver.quit()
        except:
            pass
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(service=Service("../chromedriver-mac-arm64/chromedriver"), options=chrome_options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    print("🚀 ChromeDriver started.")

def restart_driver(username, password, url):
    print("♻️ Restarting ChromeDriver...")
    start_driver()
    return selenium_login(username, password, url, skip_restart=True)

# --- Real Chrome Zoom Out ---
def real_chrome_zoom_out():
    """Maximize window and send real OS-level Cmd/Ctrl + '-' to Chrome."""
    try:
        driver.maximize_window()
        print("🖥️ Chrome window maximized")
        time.sleep(1)  # Let Chrome adjust before zoom

        for _ in range(8):  # Press multiple times to reach ~25%
            if pyautogui.platform.system() == "Darwin":  # macOS
                pyautogui.hotkey("command", "-")
            else:  # Windows/Linux
                pyautogui.hotkey("ctrl", "-")
            time.sleep(0.15)
        print("🔍 Chrome zoomed out to ~25%")
    except Exception as e:
        print(f"⚠️ Could not zoom out Chrome: {e}")

# --- Selenium login + scan ---
def selenium_login(username, password, url, skip_restart=False):
    global driver
    try:
        if not skip_restart:
            start_driver()

        driver.get(url)
        print("🌐 Navigated to URL...")

        # --- Login ---
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.NAME, "username"))
            ).send_keys(username)
            driver.find_element(By.NAME, "password").send_keys(password)
            driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
            print(f"🔐 Login attempted for user: {username}")

            # Wait for "approved" status elements to load
            WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".status-label.in-approved"))
            )
            approved_elements = driver.find_elements(By.CSS_SELECTOR, ".status-label.in-approved")
            print(f"✅ Total 'in-approved' rows found: {len(approved_elements)}")

            # ✅ Maximize and zoom out
            real_chrome_zoom_out()

            # --- Scroll vertically to load all rows ---
            try:
                scrollable_div = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.ReactVirtualized__Grid"))
                )
                last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                while True:
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                    time.sleep(0.5)
                    new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                    if new_height == last_height:
                        break
                    last_height = new_height
                print("📜 Finished vertical scroll, all rows loaded.")

                # --- Scroll horizontally to reveal all columns ---
                driver.execute_script("arguments[0].scrollLeft = arguments[0].scrollWidth", scrollable_div)
                time.sleep(0.5)
                print("➡️ Finished horizontal scroll, all columns revealed.")

            except Exception as e:
                print(f"⚠️ Could not complete scrolling: {e}")

        except Exception as e:
            print(f"⚠️ Login or initial load failed: {e}")

        # --- Detect all header columns once ---
        header_cells = driver.find_elements(By.CSS_SELECTOR, ".react-grid-HeaderCell")
        col_index_map = {}
        for i, header in enumerate(header_cells):
            col_name = header.text.strip().lower()
            if col_name:
                col_index_map[col_name] = i
        print("📊 Detected columns:", col_index_map)

        # --- Print header ---
        print("\n🧪 Results Table")
        print(f"{'Creative Name':100} {'ID':15} {'Status':20} {'Test Case 1':15} {'Test Case 2':25} {'Test Case 3':10} {'Test Case 4':10}")
        print("-" * 140)

        # --- Get all creative rows ---
        rows = driver.find_elements(By.CSS_SELECTOR, "div.react-grid-Row")

        for idx, row in enumerate(rows):
            try:
                cells = row.find_elements(By.CSS_SELECTOR, ".react-grid-Cell")

                # Creative Name
                try:
                    name_el = row.find_element(By.CSS_SELECTOR, "span.name-overflow a")
                    creative_name = name_el.text.strip()
                except:
                    creative_name = "[Missing]"

                # Creative ID (auto-detect if available)
                creative_id = cells[col_index_map.get("id", 0)].text.strip() if "id" in col_index_map else "[Missing]"

                # Status
                status_text = cells[col_index_map.get("status", 0)].text.strip() if "status" in col_index_map else "[Missing]"

                # Placement Size (auto-detect)
                if "placement size" in col_index_map:
                    ps_col_idx = col_index_map["placement size"]
                    placement_size = cells[ps_col_idx].text.strip().replace(" ", "") if ps_col_idx < len(cells) else "0x0"
                else:
                    placement_size = "0x0"

                # Type (auto-detect)
                if "type" in col_index_map:
                    type_col_idx = col_index_map["type"]
                    creative_type = cells[type_col_idx].text.strip() if type_col_idx < len(cells) else "[Missing]"
                else:
                    creative_type = "[Missing]"

                # --- TEST CASES ---
                test_case_1 = "PASSED" if "approved" in status_text.lower() else "FAIL"

                # --- TEST CASE 2 ---
                placement_required_types = ["alt image", "html_onpage", "html_expand", "html_standard"]

                if placement_size != "0x0" and creative_type.lower() in placement_required_types:
                    if placement_size in creative_name.replace(" ", ""):
                        test_case_2 = f"PASSED: {placement_size}"
                    else:
                        test_case_2 = f"FAIL: lacks {placement_size}"
                else:
                    test_case_2 = f"PASSED: {placement_size}"

                # --- TEST CASE 3 ---
                valid_formats = [".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4"]
                test_case_3 = "PASSED" if any(creative_name.lower().endswith(fmt) for fmt in valid_formats) else "FAIL: No valid format"

                # --- TEST CASE 4 ---
                creative_lower = creative_name.lower()
                image_exts = [".png", ".jpg", ".gif"]

                if any(creative_lower.endswith(ext) for ext in image_exts):
                    if creative_type.lower() == "altimage":
                        test_case_4 = f"PASSED: {creative_type}"
                    else:
                        test_case_4 = f"FAIL: {creative_type}"
                elif creative_lower.endswith(".zip"):
                    if creative_type.lower() in ["html_standard", "html_onpage"]:
                        test_case_4 = f"PASSED: {creative_type}"
                    else:
                        test_case_4 = f"FAIL: {creative_type}"
                elif creative_lower.endswith(".mp4"):
                    if creative_type.lower() == "preroll":
                        test_case_4 = f"PASSED: {creative_type}"
                    else:
                        test_case_4 = f"FAIL: {creative_type}"
                else:
                    test_case_4 = f"N/A: {creative_type}"


                # Print row results
                print(f"{creative_name:100} {creative_id:15} {status_text:20} {test_case_1:15} {test_case_2:25} {test_case_3:10} {test_case_4:10}")

            except Exception as e:
                print(f"{'[Missing]':100} {'[Missing]':15} {'[Error]':20} {'FAIL':15} {'Could not extract':25} {'FAIL':10} {'FAIL':10}")
                print(f"⚠️ Row {idx+1} failed: {e}")

        print("\n🏁 Test complete. Closing browser.")
        driver.quit()

    except WebDriverException as e:
        print(f"❌ Selenium issue: {e}. Restarting driver...")
        restart_driver(username, password, url)
    except Exception as e:
        print("❌ Error during login or scanning:")
        traceback.print_exc()

# --- Submit Handler ---
def submit():
    username = entry_username.get()
    password = entry_password.get()
    url = entry_url.get()

    if not username or not password or not url:
        messagebox.showwarning("Input Error", "Please fill in all fields.")
        return

    threading.Thread(target=selenium_login, args=(username, password, url)).start()

# --- GUI Setup ---
root = tk.Tk()
root.title("Basefile QA Test")
root.geometry("400x300")
root.resizable(False, False)

content = tk.Frame(root)
content.place(relx=0.5, rely=0.5, anchor="center")

# --- ORIGINAL VERSION (COMMENTED OUT) ---
# tk.Label(content, text="Username:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
# entry_username = tk.Entry(content, width=30)
# entry_username.grid(row=0, column=1, padx=5, pady=5)

# tk.Label(content, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
# entry_password = tk.Entry(content, show="*", width=30)
# entry_password.grid(row=1, column=1, padx=5, pady=5)

# tk.Label(content, text="URL:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
# entry_url = tk.Entry(content, width=30)
# entry_url.grid(row=2, column=1, padx=5, pady=5)

run_btn = tk.Button(content, text="Run", command=submit, width=20)
run_btn.grid(row=4, column=0, columnspan=2, pady=15)

root.mainloop()
