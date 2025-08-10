import os
import shutil
import platform
import threading
import traceback
import time
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# Optional (used for OS-level zoom)
import pyautogui

# --- Global Driver & Retry State ---
driver = None
_restart_attempts = 0
_MAX_RESTARTS = 1  # prevent infinite restart loops


# ---------- Browser Bootstrap Helpers ----------

def _find_chrome_binary_windows():
    """Try common Chrome locations on Windows and PATH."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _apply_common_options(opts):
    """Hardened default flags that work well in CI/desktops."""
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    # For stability when running in background
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--start-maximized")
    return opts


def start_driver():
    """
    Start a Chrome session using Selenium Manager (auto driver),
    falling back to Edge if Chrome fails. Avoids hardcoded driver paths.
    """
    global driver

    if driver:
        try:
            driver.quit()
        except Exception:
            pass

    system_name = platform.system()
    print(f"🔍 Detected OS: {system_name}")

    # --- Try Chrome first ---
    chrome_options = _apply_common_options(ChromeOptions())

    # Help Selenium find Chrome on Windows if needed
    if system_name == "Windows":
        chrome_binary = _find_chrome_binary_windows()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            print(f"🧭 Using Chrome binary: {chrome_binary}")
        else:
            print("⚠️ Chrome binary not found in common locations/ PATH.")

    try:
        # Selenium Manager (no explicit driver path) — downloads/locates correct driver
        driver = webdriver.Chrome(service=ChromeService(), options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        print("✅ Chrome started successfully.")
        return
    except Exception as e:
        print(f"❌ Chrome failed to start via Selenium Manager: {e}")

    # --- Fallback to Edge (also Selenium Manager) ---
    try:
        from selenium.webdriver import EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService

        edge_options = _apply_common_options(EdgeOptions())
        driver = webdriver.Edge(service=EdgeService(), options=edge_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        print("✅ Microsoft Edge started successfully (fallback).")
        return
    except Exception as e2:
        print(f"❌ Edge fallback failed: {e2}")

    # If both fail, raise a clear error
    raise RuntimeError(
        "Unable to start a WebDriver session. Ensure Chrome or Edge is installed "
        "and that this environment allows Selenium Manager to fetch drivers."
    )


def restart_driver(username, password, url):
    global _restart_attempts
    if _restart_attempts >= _MAX_RESTARTS:
        raise RuntimeError("Reached maximum restart attempts, aborting.")
    _restart_attempts += 1
    print(f"♻️ Restarting browser… (attempt #{_restart_attempts})")
    start_driver()
    return selenium_login(username, password, url, skip_restart=True)


# ---------- UX Helpers ----------

def real_chrome_zoom_out():
    """Maximize window and send real OS-level Cmd/Ctrl + '-' to the browser."""
    try:
        pyautogui.FAILSAFE = False  # avoid interruptions if mouse hits corner
        driver.maximize_window()
        print("🖥️ Browser window maximized")
        time.sleep(1)  # Let the window settle

        # Zoom out ~8 steps (~25% depending on browser)
        for _ in range(8):
            if platform.system() == "Darwin":
                pyautogui.hotkey("command", "-")
            else:
                pyautogui.hotkey("ctrl", "-")
            time.sleep(0.15)
        print("🔍 Browser zoomed out to ~25%")
    except Exception as e:
        print(f"⚠️ Could not zoom out browser: {e}")


def reset_zoom():
    """Restore browser zoom to 100% (OS-level)."""
    try:
        if platform.system() == "Darwin":
            pyautogui.hotkey("command", "0")  # Cmd + 0
        else:
            pyautogui.hotkey("ctrl", "0")     # Ctrl + 0
        time.sleep(0.2)
        print("🔄 Browser zoom reset to 100%")
    except Exception as e:
        print(f"⚠️ Could not reset zoom: {e}")


# ---------- Main Selenium Flow ----------

def selenium_login(username, password, url, skip_restart=False):
    """
    Navigate to the given URL, perform login, scan grid, and print checks.
    """
    global driver
    try:
        if not skip_restart:
            start_driver()

        print(f"🌐 Navigating to URL: {url}")
        driver.get(url)

        # --- Login ---
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.NAME, "username"))
            ).send_keys(username)
            driver.find_element(By.NAME, "password").send_keys(password)
            driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
            print(f"🔐 Login attempted for user: {username}")

            # Wait for 'approved' status elements to load
            WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".status-label.in-approved"))
            )
            approved_elements = driver.find_elements(By.CSS_SELECTOR, ".status-label.in-approved")
            print(f"✅ Total 'in-approved' rows found: {len(approved_elements)}")

            # Maximize and zoom out
            real_chrome_zoom_out()

            # --- Scroll to load all rows/columns ---
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
        print(f"{'Creative Name':50} {'ID':10} {'Status':10} {'TC1':8} {'TC2':20} {'TC3':15} {'TC4':20} {'TC5':20} {'TC6':15} {'TC7':30} {'TC8':30} {'TC9':20}")
        print("-" * 250)

        # --- Get all creative rows ---
        rows = driver.find_elements(By.CSS_SELECTOR, "div.react-grid-Row")

        for idx, row in enumerate(rows):
            try:
                cells = row.find_elements(By.CSS_SELECTOR, ".react-grid-Cell")

                # Creative Name
                try:
                    name_el = row.find_element(By.CSS_SELECTOR, "span.name-overflow a")
                    creative_name = name_el.text.strip()
                except Exception:
                    creative_name = "[Missing]"

                # Creative ID
                creative_id = cells[col_index_map.get("id", 0)].text.strip() if "id" in col_index_map else "[Missing]"

                # Status
                status_text = cells[col_index_map.get("status", 0)].text.strip() if "status" in col_index_map else "[Missing]"

                # Placement Size
                if "placement size" in col_index_map:
                    ps_col_idx = col_index_map["placement size"]
                    placement_size = cells[ps_col_idx].text.strip().replace(" ", "") if ps_col_idx < len(cells) else "0x0"
                else:
                    placement_size = "0x0"

                # Type
                if "type" in col_index_map:
                    type_col_idx = col_index_map["type"]
                    creative_type = cells[type_col_idx].text.strip() if type_col_idx < len(cells) else "[Missing]"
                else:
                    creative_type = "[Missing]"

                # --- TEST CASE 1 ---
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

                # Normalize type
                ctype = creative_type.lower().replace(" ", "")
                if any(creative_lower.endswith(ext) for ext in image_exts):
                    test_case_4 = "PASSED: altimage" if ctype == "altimage" else f"FAIL: {creative_type}"
                elif creative_lower.endswith(".zip"):
                    test_case_4 = "PASSED: html" if ctype in ["html_standard", "html_onpage", "htmlstandard", "htmlonpage"] else f"FAIL: {creative_type}"
                elif creative_lower.endswith(".mp4"):
                    test_case_4 = "PASSED: preroll" if ctype == "preroll" else f"FAIL: {creative_type}"
                else:
                    test_case_4 = f"N/A: {creative_type}"

                # --- TEST CASE 5 ---
                try:
                    if "base file size" in col_index_map:
                        bfs_col_idx = col_index_map["base file size"]
                        size_text = cells[bfs_col_idx].text.strip().lower()

                        size_kb = 0.0
                        if "mb" in size_text:
                            size_kb = float(size_text.replace("mb", "").strip()) * 1024
                        elif "kb" in size_text:
                            size_kb = float(size_text.replace("kb", "").strip())
                        else:
                            try:
                                size_kb = float(size_text)
                            except Exception:
                                size_kb = 0.0

                        if ctype in ["preroll", "vastaudio"]:
                            test_case_5 = "PASSED: No size limit"
                        else:
                            if size_kb <= 600:
                                test_case_5 = f"PASSED: {size_kb:.0f} KB"
                            else:
                                test_case_5 = f"FAIL: {size_kb:.0f} KB > 600 KB"
                    else:
                        test_case_5 = "[Missing Base File Size]"
                except Exception as e:
                    test_case_5 = f"FAIL: Size check error ({e})"

                # --- TEST CASE 6 ---
                test_case_6 = "PASSED: Auto-pass for 1x1" if placement_size.lower() == "1x1" else "N/A: not 1x1"

                # --- TEST CASE 7 ---
                try:
                    file_name_col = cells[col_index_map["file name"]].text.strip() if "file name" in col_index_map else ""
                    test_case_7 = "PASSED: Matches" if creative_name.lower() == file_name_col.lower() else f"FAIL: '{creative_name}' != '{file_name_col}'"
                except Exception:
                    test_case_7 = "FAIL: Missing"

                # --- TEST CASE 8 ---  (fixed)
                if ctype in ["preroll", "vastaudio"]:
                    duration_values = ["6", "10", "15", "20", "30", "60", "90", "120"]
                    aspect_ratios = ["16x9", "4x3", "1x1", "9x16"]

                    has_duration = any(dur in creative_lower for dur in duration_values)
                    has_ratio = any(ratio in creative_lower for ratio in aspect_ratios)

                    if has_duration and has_ratio:
                        test_case_8 = "PASSED: Duration & Ratio found"
                    elif not has_duration and not has_ratio:
                        test_case_8 = "FAIL: Missing duration & ratio"
                    elif not has_duration:
                        test_case_8 = "FAIL: Missing duration"
                    else:
                        test_case_8 = "FAIL: Missing ratio"
                else:
                    test_case_8 = "N/A"

                # --- TEST CASE 9 ---
                if creative_lower.endswith(".mp3"):
                    test_case_9 = "PASSED: vastaudio" if ctype == "vastaudio" else f"FAIL: {creative_type}"
                else:
                    test_case_9 = f"N/A: {creative_type}"

                print(f"{creative_name:50} {creative_id:10} {status_text:10} {test_case_1:8} {test_case_2:20} {test_case_3:15} {test_case_4:20} {test_case_5:20} {test_case_6:15} {test_case_7:30} {test_case_8:30} {test_case_9:20}")

            except Exception as e:
                print(f"{'[Missing]':100} {'[Missing]':15} {'[Error]':20} {'FAIL':15} {'Could not extract':25} {'FAIL':20} {'FAIL':20} {'FAIL':25} {'FAIL':30} {'FAIL':30} {'FAIL':30} {'FAIL':30}")
                print(f"⚠️ Row {idx+1} failed: {e}")

        # ✅ Reset zoom after finishing TC#9 for all rows
        time.sleep(1)  # Add 1 second delay
        reset_zoom()

        print("\n🏁 Test complete. Browser will remain open.")

        # print("\n🏁 Test complete. Closing browser.")
        # try:
        #     driver.quit()
        # except Exception:
        #     pass

    except WebDriverException as e:
        print(f"❌ Selenium issue: {e}. Restarting browser…")
        restart_driver(username, password, url)
    except Exception:
        print("❌ Error during login or scanning:")
        traceback.print_exc()
        try:
            if driver:
                # Try to reset zoom even on failure so the browser is not left tiny
                reset_zoom()
                driver.quit()
        except Exception:
            pass


# ---------- GUI ----------

def submit():
    username = entry_username.get().strip()
    password = entry_password.get().strip()
    url = entry_url.get().strip()

    if not username or not password or not url:
        messagebox.showwarning("Input Error", "Please fill in all fields.")
        return

    t = threading.Thread(target=selenium_login, args=(username, password, url), daemon=True)
    t.start()


# --- GUI Setup ---
root = tk.Tk()
root.title("Basefile QA - East Coast")
root.geometry("400x300")
root.resizable(False, False)

content = tk.Frame(root)
content.place(relx=0.5, rely=0.5, anchor="center")

tk.Label(content, text="Username:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
entry_username = tk.Entry(content, width=30)
entry_username.insert(0, os.getenv("FT_USERNAME", ""))  # safer than hardcoding
entry_username.grid(row=0, column=1, padx=5, pady=5)

tk.Label(content, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
entry_password = tk.Entry(content, show="*", width=30)
entry_password.insert(0, os.getenv("FT_PASSWORD", ""))  # safer than hardcoding
entry_password.grid(row=1, column=1, padx=5, pady=5)

tk.Label(content, text="URL:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
entry_url = tk.Entry(content, width=30)
entry_url.insert(0, os.getenv("FT_URL", "https://creative-manager.flashtalking.net/library/193436/"))
entry_url.grid(row=2, column=1, padx=5, pady=5)

run_btn = tk.Button(content, text="Run", command=submit, width=20)
run_btn.grid(row=4, column=0, columnspan=2, pady=15)

root.mainloop()
