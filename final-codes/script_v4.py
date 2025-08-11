import os
import shutil
import platform
import threading
import traceback
import time
from pathlib import Path

import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, TimeoutException
from urllib.parse import urlparse

# Optional (used for OS-level zoom)
import pyautogui

# --- Global Driver & Retry State ---
driver = None
_restart_attempts = 0
_MAX_RESTARTS = 1  # prevent infinite restart loops

# --- GUI refs (set later) ---
log_text = None
root = None

# --- Your exact XPaths (added) ---
XPATH_PREVIEWS_BTN_SPAN = "/html/body/main/section/div[2]/div[1]/div[2]/div[3]/div[1]/div/button/span"
XPATH_PREVIEW_CREATIVE_PRIVATE = "/html/body/div[2]/div[3]/nav/div[2]/div/span"


# ------------------------------
# Console logger (terminal only)
# ------------------------------
def log(message: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {message}")


# ------------------------------
# Pretty GUI log helpers
# ------------------------------
def gui_init_tags():
    """Setup text tags for colors/styles."""
    try:
        log_text.tag_configure("header", font=("Segoe UI", 10, "bold"))
        log_text.tag_configure("label", font=("Consolas", 9))
        log_text.tag_configure("pass", foreground="#0a7f24", font=("Consolas", 9, "bold"))
        log_text.tag_configure("fail", foreground="#c1121f", font=("Consolas", 9, "bold"))
        log_text.tag_configure("na", foreground="#6b7280", font=("Consolas", 9, "italic"))
        log_text.tag_configure("url", foreground="#0369a1", font=("Consolas", 9))
        log_text.tag_configure("dim", foreground="#6b7280")
        log_text.tag_configure("divider", foreground="#9ca3af")
        log_text.tag_configure("name", foreground="#374151")
    except Exception:
        pass


def _gui_write(text, *tags):
    """Append text to GUI log on UI thread."""
    def _do():
        try:
            log_text.configure(state="normal")
            log_text.insert("end", text, tags)
            log_text.see("end")
            log_text.configure(state="disabled")
        except Exception:
            pass
    try:
        root.after(0, _do)
    except Exception:
        pass


def gui_log_result(creative_id, creative_name, cases_dict, url):
    """
    Pretty block:
    ────────────
    Creative ID: 5460184  • Name: AudioBanner_300x250.jpg
      TC1: PASSED
      TC2: FAIL
      ...
    Done checking for creative <URL: https://...>
    ────────────
    """
    # Divider
    _gui_write("────────────────────────────────────────────────────────\n", "divider")

    # Header
    _gui_write("Creative ID: ", "header")
    _gui_write(str(creative_id or "N/A") + "  ", "header")
    if creative_name and creative_name != "[Missing]":
        _gui_write("• Name: ", "name")
        _gui_write(creative_name + "\n", "name")
    else:
        _gui_write("\n",)

    # Body (TEST CASE #1 TO TEST CASE #11 in order)
    ordered_keys = [f"TC{i}" for i in range(1, 12)]
    for key in ordered_keys:
        value = cases_dict.get(key, "-")
        tag = "label"
        vlow = (value or "").lower()
        if "pass" in vlow:
            tag = "pass"
        elif "fail" in vlow:
            tag = "fail"
        elif "n/a" in vlow or value == "-":
            tag = "na"

        _gui_write(f"  {key}: ", "label")
        _gui_write(f"{value}\n", tag)

    # URL line
    if url:
        _gui_write("Done checking for creative <URL: ", "dim")
        _gui_write(url, "url")
        _gui_write(">\n", "dim")
    else:
        _gui_write("Done checking for creative <URL: N/A>\n", "dim")

    # End divider
    _gui_write("────────────────────────────────────────────────────────\n\n", "divider")


def focus_app_window():
    """Bring the Tk window to the front and give it focus."""
    try:
        root.deiconify()
        root.lift()
        root.focus_force()
        root.attributes("-topmost", True)
        root.after(300, lambda: root.attributes("-topmost", False))
    except Exception as e:
        log(f"⚠️ Could not refocus GUI: {e}")


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
    log(f"🔍 Detected OS: {system_name}")

    # --- Try Chrome first ---
    chrome_options = _apply_common_options(ChromeOptions())
    # Enable browser console logs for TC11
    chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

    # Help Selenium find Chrome on Windows if needed
    if system_name == "Windows":
        chrome_binary = _find_chrome_binary_windows()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            log(f"🧭 Using Chrome binary: {chrome_binary}")
        else:
            log("⚠️ Chrome binary not found in common locations/ PATH.")

    try:
        # Selenium Manager (no explicit driver path) — downloads/locates correct driver
        driver = webdriver.Chrome(service=ChromeService(), options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        log("✅ Chrome started successfully.")
        return
    except Exception as e:
        log(f"❌ Chrome failed to start via Selenium Manager: {e}")

    # --- Fallback to Edge (also Selenium Manager) ---
    try:
        from selenium.webdriver import EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService

        edge_options = _apply_common_options(EdgeOptions())
        # Enable browser console logs for TC11
        edge_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

        driver = webdriver.Edge(service=EdgeService(), options=edge_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        log("✅ Microsoft Edge started successfully (fallback).")
        return
    except Exception as e2:
        log(f"❌ Edge fallback failed: {e2}")

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
    log(f"♻️ Restarting browser… (attempt #{_restart_attempts})")
    start_driver()
    return selenium_login(username, password, url, skip_restart=True)


# ---------- UX Helpers ----------

def real_chrome_zoom_out():
    """Maximize window and send real OS-level Cmd/Ctrl + '-' to the browser."""
    try:
        pyautogui.FAILSAFE = False
        driver.maximize_window()
        log("🖥️ Browser window maximized")
        time.sleep(1)
        time.sleep(1)

        for _ in range(8):
            if platform.system() == "Darwin":
                pyautogui.hotkey("command", "-")
            else:
                pyautogui.hotkey("ctrl", "-")
            time.sleep(0.15)
        log("🔍 Browser zoomed out to ~25%")
    except Exception as e:
        log(f"⚠️ Could not zoom out browser: {e}")


def reset_zoom():
    """Restore browser zoom to 100% (OS-level)."""
    try:
        if platform.system() == "Darwin":
            pyautogui.hotkey("command", "0")
        else:
            pyautogui.hotkey("ctrl", "0")
        time.sleep(0.2)
        log("🔄 Browser zoom reset to 100%")
    except Exception as e:
        log(f"⚠️ Could not reset zoom: {e}")


# ---------- Helpers for grid/checkbox & Previews ----------

def _scroll_into_view(el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.1)
    except Exception:
        pass

def _click_checkbox_in_row(row):
    """
    Try several strategies to click the row's checkbox (left-most column in Innovid grid).
    Returns True if a click was attempted successfully, else False.
    """
    try:
        cb = row.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
        _scroll_into_view(cb)
        driver.execute_script("arguments[0].click();", cb)
        return True
    except Exception:
        pass

    try:
        toggle = row.find_element(By.CSS_SELECTOR, "label, [role='checkbox'], .checkbox, .check")
        _scroll_into_view(toggle)
        driver.execute_script("arguments[0].click();", toggle)
        return True
    except Exception:
        pass

    try:
        first_cell = row.find_elements(By.CSS_SELECTOR, ".react-grid-Cell")[0]
        _scroll_into_view(first_cell)
        driver.execute_script("arguments[0].click();", first_cell)
        return True
    except Exception:
        pass

    return False

def _safe_click(el):
    try:
        _scroll_into_view(el)
    except Exception:
        pass
    try:
        ActionChains(driver).move_to_element(el).pause(0.05).click(el).perform()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            try:
                el.send_keys(Keys.ENTER)
                return True
            except Exception:
                return False

def _open_preview_for_selected():
    """
    Click 'Previews' → 'Preview Creative (Private)' and switch to the new tab.
    Uses several resilient strategies and retries. Returns the preview tab handle.
    """
    handles_before = set(driver.window_handles)

    # Previews button locators
    preview_btn_locators = [
        (By.XPATH, XPATH_PREVIEWS_BTN_SPAN + "/ancestor::button[1]"),
        (By.XPATH, "(//button[.//span[normalize-space()='Previews']])[1]"),
        (By.XPATH, "//div[contains(@class,'toolbar') or contains(@class,'bulk') or contains(@class,'button-side')]//button[.//span[contains(normalize-space(),'Previews')]]"),
        (By.XPATH, "//button[contains(normalize-space(.), 'Previews')]"),
    ]

    # Menu container & item
    menu_container_xpath = ("//nav[contains(@class,'react-contextmenu') and "
                            "(contains(@class,'is-open') or contains(@class,'react-contextmenu--visible') or @style[contains(.,'opacity: 1')])]")
    menu_item_locators = [
        (By.XPATH, XPATH_PREVIEW_CREATIVE_PRIVATE),
        (By.XPATH, menu_container_xpath + "//div[contains(@class,'react-contextmenu-item') and not(contains(@class,'disabled'))][.//span[contains(normalize-space(),'Preview Creative')]]"),
        (By.XPATH, "//span[contains(normalize-space(),'Preview Creative')]"),
    ]

    # Click Previews button (retries)
    previews_clicked = False
    for attempt in range(3):
        btn = None
        for by, sel in preview_btn_locators:
            try:
                btn = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((by, sel)))
                break
            except Exception:
                continue
        if not btn:
            continue

        if _safe_click(btn):
            try:
                WebDriverWait(driver, 6).until(EC.visibility_of_element_located((By.XPATH, menu_container_xpath)))
                previews_clicked = True
                break
            except Exception:
                time.sleep(0.2)
                continue

    if not previews_clicked:
        raise TimeoutException("Could not open 'Previews' menu.")

    # Click the 'Preview Creative' item
    item = None
    for by, sel in menu_item_locators:
        try:
            item = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((by, sel)))
            break
        except Exception:
            continue
    if not item:
        raise TimeoutException("Menu item 'Preview Creative' not found/clickable.")

    if not _safe_click(item):
        raise TimeoutException("Failed to click 'Preview Creative'.")

    # Switch to new preview tab
    WebDriverWait(driver, 15).until(lambda d: len(d.window_handles) > len(handles_before))
    preview_handle = [h for h in driver.window_handles if h not in handles_before][-1]
    driver.switch_to.window(preview_handle)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    log(f"🆕 Preview tab opened. Title: {driver.title!r}, URL: {driver.current_url}")
    return preview_handle

def _get_largest_iframe():
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if not iframes:
        return None
    largest = None
    largest_area = -1
    for f in iframes:
        try:
            rect = driver.execute_script(
                "var r=arguments[0].getBoundingClientRect(); return {w:r.width,h:r.height};", f
            )
            area = float(rect.get("w", 0)) * float(rect.get("h", 0))
            if area > largest_area:
                largest_area = area
                largest = f
        except Exception:
            continue
    return largest

def _click_creative_in_preview():
    """
    In the Preview tab, click the anchor inside iframe#ad to open the click-through.
    Returns (detected_standard_clicktag: bool, click_tab_handle or None).
    """
    from selenium.common.exceptions import TimeoutException

    reset_zoom(); time.sleep(0.2)

    handles_before = set(driver.window_handles)

    # Enter the preview iframe
    try:
        try:
            frame = WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#ad"))
            )
        except TimeoutException:
            frame = _get_largest_iframe()
            if not frame:
                raise TimeoutException("Preview iframe not found")
        driver.switch_to.frame(frame)

        # Anchor to click (prefer /clicktag/)
        try:
            anchor = WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/clicktag']"))
            )
        except TimeoutException:
            anchors = driver.find_elements(By.CSS_SELECTOR, "a[target='_blank'], a[href]")
            if not anchors:
                raise TimeoutException("No anchor elements found in preview")
            # choose the largest
            best, area = None, -1
            for a in anchors:
                try:
                    ar = driver.execute_script(
                        "var r=arguments[0].getBoundingClientRect(); return Math.max(0,r.width*r.height);", a
                    )
                    if ar > area: best, area = a, ar
                except Exception:
                    pass
            anchor = best or anchors[0]

        href = anchor.get_attribute("href")
        try:
            _scroll_into_view(anchor)
        except Exception:
            pass

        opened = False
        try:
            ActionChains(driver).move_to_element(anchor).pause(0.05).click(anchor).perform()
            WebDriverWait(driver, 4).until(lambda d: len(d.window_handles) > len(handles_before))
            opened = True
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", anchor)
                WebDriverWait(driver, 4).until(lambda d: len(d.window_handles) > len(handles_before))
                opened = True
            except Exception:
                pass

        if not opened and href:
            driver.execute_script("window.open(arguments[0], '_blank');", href)
            WebDriverWait(driver, 6).until(lambda d: len(d.window_handles) > len(handles_before))

    finally:
        driver.switch_to.default_content()

    # Switch to the new tab
    click_handle = [h for h in driver.window_handles if h not in handles_before]
    click_handle = click_handle[-1] if click_handle else None
    if click_handle:
        driver.switch_to.window(click_handle)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")

    # Detect "Standard click tag"
    detected = False
    if click_handle:
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH,
                    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'standard click tag')]"))
            )
            detected = True
        except Exception:
            detected = False

    log(f"{'✅' if detected else '❌'} ClickTag page {'detected' if detected else 'not detected'}."
        f" Title={driver.title!r}, URL={driver.current_url}")
    return detected, click_handle

def _check_preview_console_errors():
    """
    Read browser console logs in the *Preview* tab and only flag errors that
    originate from the ad iframe (e.g., https://api.flashtalking.net/lcrp/tia/...).
    Returns (has_errors: bool, errors: list[str]).
    """
    allowed_patterns = []
    try:
        frame = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#ad"))
        )
        src = (frame.get_attribute("src") or "").strip()
        if src:
            u = urlparse(src)
            allowed_patterns = [
                f"{u.scheme}://{u.netloc}/lcrp/",
                u.netloc,
            ]
    except Exception:
        return False, []

    ignore_substrings = [
        "/crm/v1/user",
        "/int/v1/ui/creative-libraries",
        "grafana/faro-web-sdk",
        "Problem Starting up Pendo",
        "DEPRECATED_ENDPOINT",
        "SharedImageManager::ProduceMemory",
    ]

    try:
        _ = driver.get_log('browser')
    except Exception:
        pass
    time.sleep(0.15)

    errors = []
    try:
        logs = driver.get_log('browser')
        for entry in logs:
            lvl = (entry.get('level') or '').upper()
            msg = entry.get('message') or ''
            if lvl not in ('SEVERE', 'ERROR'):
                continue
            if any(s in msg for s in ignore_substrings):
                continue
            if allowed_patterns and not any(p in msg for p in allowed_patterns):
                continue
            errors.append(f"[{lvl}] {msg}")
    except Exception as e:
        log(f"ℹ️ Console logs not available: {e}")

    return (len(errors) > 0), errors


# ---------- Main Selenium Flow ----------

def selenium_login(username, password, url, skip_restart=False):
    """
    Navigate to the given URL, perform login, scan grid, and print checks.
    """
    global driver
    try:
        if not skip_restart:
            start_driver()

        log(f"🌐 Navigating to URL: {url}")
        driver.get(url)

        # --- Login ---
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.NAME, "username"))
            ).send_keys(username)
            driver.find_element(By.NAME, "password").send_keys(password)
            driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
            log(f"🔐 Login attempted for user: {username}")

            WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".status-label.in-approved"))
            )
            approved_elements = driver.find_elements(By.CSS_SELECTOR, ".status-label.in-approved")
            log(f"✅ Total 'in-approved' rows found: {len(approved_elements)}")

            real_chrome_zoom_out()

            # Load all rows/columns
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
                log("📜 Finished vertical scroll, all rows loaded.")

                driver.execute_script("arguments[0].scrollLeft = arguments[0].scrollWidth", scrollable_div)
                time.sleep(0.5)
                log("➡️ Finished horizontal scroll, all columns revealed.")
            except Exception as e:
                log(f"⚠️ Could not complete scrolling: {e}")

        except Exception as e:
            log(f"⚠️ Login or initial load failed: {e}")

        # Detect headers
        header_cells = driver.find_elements(By.CSS_SELECTOR, ".react-grid-HeaderCell")
        col_index_map = {}
        for i, header in enumerate(header_cells):
            col_name = header.text.strip().lower()
            if col_name:
                col_index_map[col_name] = i
        log(f"📊 Detected columns: {col_index_map}")

        # Console table header
        log("\n🧪 Results Table")
        log(f"{'Creative Name':50} {'ID':10} {'Status':10} {'TC1':8} {'TC2':20} {'TC3':15} {'TC4':20} {'TC5':20} {'TC6':15} {'TC7':30} {'TC8':30} {'TC9':20} {'TC10':10} {'TC11':10}")
        log("-" * 285)

        rows = driver.find_elements(By.CSS_SELECTOR, "div.react-grid-Row")

        for idx, row in enumerate(rows):
            try:
                cells = row.find_elements(By.CSS_SELECTOR, ".react-grid-Cell")

                # Name + URL
                creative_url = ""
                try:
                    name_el = row.find_element(By.CSS_SELECTOR, "span.name-overflow a")
                    creative_name = name_el.text.strip()
                    creative_url = (name_el.get_attribute("href") or "").strip()
                except Exception:
                    creative_name = "[Missing]"

                # ID
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

                # --- TEST CASE #1 ---
                ##############################################
                ## ONLY THOSE CREATIVE WHOSE STATUS IS "FOR QA"
                ##############################################
                test_case_1 = "PASSED" if "approved" in status_text.lower() else "FAIL"

                # --- TEST CASE #2 ---
                ##############################################
                ## CREATIVE NAME MUST CONTAIN PLACEMENT SIZE FOR FORMATS:
                ## alt image, html_onpage, html_expand, html_standard
                ##############################################
                placement_required_types = ["alt image", "html_onpage", "html_expand", "html_standard"]
                if placement_size != "0x0" and creative_type.lower() in placement_required_types:
                    if placement_size in creative_name.replace(" ", ""):
                        test_case_2 = f"PASSED"
                    else:
                        test_case_2 = f"FAIL"
                else:
                    test_case_2 = f"PASSED"

                # --- TEST CASE #3 ---
                ##############################################
                ## CREATIVE NAME MUST CONTAIN FILE FORMAT AS SUFFIX
                ##############################################
                valid_formats = [".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4"]
                test_case_3 = "PASSED" if any(creative_name.lower().endswith(fmt) for fmt in valid_formats) else "FAIL"

                # --- TEST CASE #4 ---
                ##############################################
                ## ALT IMAGE IF CREATIVE IS: [png, jpg, gif]
                ## PREROLL IF CREATIVE IS: [mp4]
                ## HTML_STANDARD, HTML_ONPAGE IF CREATIVE IS: [zip]
                ##############################################
                creative_lower = creative_name.lower()
                image_exts = [".png", ".jpg", ".gif"]
                ctype = creative_type.lower().replace(" ", "")
                if any(creative_lower.endswith(ext) for ext in image_exts):
                    test_case_4 = "PASSED" if ctype == "altimage" else "FAIL"
                elif creative_lower.endswith(".zip"):
                    test_case_4 = "PASSED" if ctype in ["html_standard", "html_onpage", "htmlstandard", "htmlonpage"] else "FAIL"
                elif creative_lower.endswith(".mp4"):
                    test_case_4 = "PASSED" if ctype == "preroll" else "FAIL"
                else:
                    test_case_4 = "N/A"

                # --- TEST CASE #5 ---
                ##############################################
                ## BASE FILE SIZE MUST BE LESS THAN 600KB
                ## EXCEPT FOR PREROLL & VAST AUDIO
                ##############################################
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
                            test_case_5 = "PASSED"
                        else:
                            test_case_5 = "PASSED" if size_kb <= 600 else "FAIL"
                    else:
                        test_case_5 = "N/A"
                except Exception:
                    test_case_5 = "FAIL"

                # --- TEST CASE #6 ---
                ##############################################
                ## PLACEMENT SIZE IS: 1x1
                ## AUTO APPROVE!
                ##############################################
                test_case_6 = "PASSED" if placement_size.lower() == "1x1" else "N/A"

                # --- TEST CASE #7 ---
                ##############################################
                ## CREATIVE NAME IS SAME WITH FILE NAME
                ##############################################
                try:
                    file_name_col = cells[col_index_map["file name"]].text.strip() if "file name" in col_index_map else ""
                    test_case_7 = "PASSED" if creative_name.lower() == file_name_col.lower() else "FAIL"
                except Exception:
                    test_case_7 = "FAIL"

                # --- TEST CASE #8 ---
                ##############################################
                ## FOR PREROLL & VAST AUDIO:
                ## CREATIVE FILE NAME USUALLY HAS: DURATION & ASPECT RATIO
                ## EXAMPLE: 15_16x9-0TT.mp4
                ## > 15 video duration
                ## > 16x9 ratio [1920x1080px]
                ##############################################
                if ctype in ["preroll", "vastaudio"]:
                    duration_values = ["6", "10", "15", "20", "30", "60", "90", "120"]
                    aspect_ratios = ["16x9", "4x3", "1x1", "9x16"]
                    has_duration = any(dur in creative_lower for dur in duration_values)
                    has_ratio = any(ratio in creative_lower for ratio in aspect_ratios)
                    if has_duration and has_ratio:
                        test_case_8 = "PASSED"
                    else:
                        test_case_8 = "FAIL"
                else:
                    test_case_8 = "N/A"

                # --- TEST CASE #9 ---
                ##############################################
                ## VAST AUDIO TYPE IF IT IS: [mp3]
                ##############################################
                if creative_lower.endswith(".mp3"):
                    test_case_9 = "PASSED" if ctype == "vastaudio" else "FAIL"
                else:
                    test_case_9 = "N/A"

                # --- TEST CASE #10 & #11 ---
                ##############################################
                ## EXCEPT MP3:
                ## CLICKTAG should be working
                ## NO ERROR IN CONSOLE
                ##############################################
                last_checked_url = creative_url or ""
                if creative_lower.endswith(".mp3"):
                    tc10_status = "-"
                    tc11_status = "N/A"
                else:
                    tc10_status = "-"
                    tc11_status = "-"

                    reset_zoom()
                    clicked = _click_checkbox_in_row(row)

                    if clicked:
                        root_handle = driver.current_window_handle
                        preview_handle = None
                        click_handle = None
                        try:
                            preview_handle = _open_preview_for_selected()
                            try:
                                last_checked_url = driver.current_url
                            except Exception:
                                pass

                            has_errors, errs = _check_preview_console_errors()
                            if has_errors:
                                tc11_status = "FAIL"
                                log("❌ TC11 console errors detected:")
                                for e in errs[:10]:
                                    log("    " + e[:500])
                            else:
                                tc11_status = "PASSED"
                                log("✅ TC11: No console errors detected in Preview.")

                            detected, click_handle = _click_creative_in_preview()
                            tc10_status = "PASSED" if detected else "FAIL"
                            log(f"TC10 ClickTag: {tc10_status}")

                        except Exception as e:
                            log(f"⚠️ TC10/11 preview flow error: {e}")
                        finally:
                            try:
                                if click_handle and click_handle in driver.window_handles:
                                    driver.switch_to.window(click_handle)
                                    driver.close()
                            except Exception:
                                pass
                            try:
                                if preview_handle and preview_handle in driver.window_handles:
                                    driver.switch_to.window(preview_handle)
                                    driver.close()
                            except Exception:
                                pass
                            try:
                                if root_handle in driver.window_handles:
                                    driver.switch_to.window(root_handle)
                            except Exception:
                                pass
                            try:
                                _click_checkbox_in_row(row)
                                log("☑️ Row unchecked.")
                            except Exception as ue:
                                log(f"⚠️ Could not uncheck row: {ue}")
                    else:
                        tc10_status = "NOT FOUND/CLICKABLE"

                # Console row (kept)
                log(f"{creative_name:50} {creative_id:10} {status_text:10} {test_case_1:8} {test_case_2:20} {test_case_3:15} {test_case_4:20} {test_case_5:20} {test_case_6:15} {test_case_7:30} {test_case_8:30} {test_case_9:20} {tc10_status:10} {tc11_status:10}")

                # GUI pretty row
                cases = {
                    "1]Creative with QA STATUS": test_case_1, "2]Creative name has PLACEMENT size": test_case_2, "3]": test_case_3, "TC4": test_case_4,
                    "TC5": test_case_5, "TC6": test_case_6, "TC7": test_case_7, "TC8": test_case_8,
                    "TC9": test_case_9, "TC10": tc10_status, "TC11": tc11_status
                }
                gui_log_result(creative_id, creative_name, cases, last_checked_url)

            except Exception as e:
                log(f"{'[Missing]':100} {'[Missing]':15} {'[Error]':20} {'FAIL':15} {'Could not extract':25} {'FAIL':20} {'FAIL':20} {'FAIL':25} {'FAIL':30} {'FAIL':30} {'FAIL':30} {'FAIL':30} {'-':10} {'-':10}")
                log(f"⚠️ Row {idx+1} failed: {e}")

    except WebDriverException as e:
        log(f"❌ Selenium issue: {e}. Restarting browser…")
        restart_driver(username, password, url)
    except Exception:
        log("❌ Error during login or scanning:")
        try:
            log(traceback.format_exc())
        except Exception:
            pass
        try:
            if driver:
                reset_zoom()
                driver.quit()
        except Exception:
            pass
    finally:
        try:
            root.after(0, focus_app_window)
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
root.geometry("900x660")
root.resizable(True, True)

# Inputs container (top)
content = tk.Frame(root)
content.place(relx=0.5, rely=0.06, anchor="n")

tk.Label(content, text="Username:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
entry_username = tk.Entry(content, width=40)
entry_username.insert(0, os.getenv("FT_USERNAME", ""))
entry_username.grid(row=0, column=1, padx=5, pady=5)

tk.Label(content, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
entry_password = tk.Entry(content, show="*", width=40)
entry_password.insert(0, os.getenv("FT_PASSWORD", ""))
entry_password.grid(row=1, column=1, padx=5, pady=5)

tk.Label(content, text="URL:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
entry_url = tk.Entry(content, width=60)
entry_url.insert(0, os.getenv("FT_URL", ""))
entry_url.grid(row=2, column=1, padx=5, pady=5)

run_btn = tk.Button(content, text="Run", command=submit, width=20)
run_btn.grid(row=3, column=0, columnspan=2, pady=12)

# Pretty Log display (bottom)
log_text = scrolledtext.ScrolledText(root, state="disabled", wrap="word", font=("Segoe UI", 10))
log_text.place(relx=0.5, rely=1.0, anchor="s", relwidth=0.95, height=470, x=0, y=-10)
gui_init_tags()
_gui_write("✨ Results will be summarized here as each creative is processed.\n\n", "dim")

root.mainloop()
