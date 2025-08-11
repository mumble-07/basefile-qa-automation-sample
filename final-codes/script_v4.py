import os
import shutil
import platform
import threading
import traceback
import time
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import font as tkfont

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
from urllib.parse import urlparse

# Optional (used for OS-level zoom)
import pyautogui

# --- Global Driver & Retry State ---
driver = None
_restart_attempts = 0
_MAX_RESTARTS = 1  # prevent infinite restart loops

# --- Processing mode (set at submit) ---
PROCESS_ALL = False  # False => QA-only; True => check all
SUMMARY_PREFIX = "For QA creatives processed: "

# --- GUI refs & fonts (set later) ---
log_text = None
root = None
UI_FONT = ("Segoe UI", 10)
TITLE_FONT = ("Segoe UI", 13, "bold")
MONO_FONT = ("Consolas", 10)
summary_var = None
check_all_var = None   # tk.BooleanVar
clear_display_var = None  # tk.BooleanVar

# --- Credentials file ---
CREDENTIALS_FILE = Path(__file__).resolve().parent / "credentials.txt"

# --- Your exact XPaths (added) ---
XPATH_PREVIEWS_BTN_SPAN = "/html/body/main/section/div[2]/div[1]/div[2]/div[3]/div[1]/div/button/span"
XPATH_PREVIEW_CREATIVE_PRIVATE = "/html/body/div[2]/div[3]/nav/div[2]/div/span"

# --- Pretty labels that mirror your comments per TC ---
CASE_LABELS = {
    "TC1":  "1] ONLY THOSE CREATIVE WHOSE STATUS IS \"FOR QA\"",
    "TC2":  "2] CREATIVE NAME MUST CONTAIN PLACEMENT SIZE (alt image / html_onpage / html_expand / html_standard)",
    "TC3":  "3] CREATIVE NAME MUST CONTAIN FILE FORMAT AS SUFFIX",
    "TC4":  "4] TYPE MUST MATCH EXTENSION (altimage: png/jpg/gif • preroll: mp4 • html_standard/html_onpage: zip)",
    "TC5":  "5] BASE FILE SIZE MUST BE ≤ 600KB (EXCEPT PREROLL & VAST AUDIO)",
    "TC6":  "6] PLACEMENT SIZE 1x1 → AUTO APPROVE",
    "TC7":  "7] CREATIVE NAME IS SAME WITH FILE NAME COLUMN",
    "TC8":  "8] (PREROLL/VASTAUDIO) FILE NAME HAS DURATION & ASPECT RATIO (e.g., 15_16x9-OTT.mp4)",
    "TC9":  "9] MP3 MUST BE VASTAUDIO TYPE",
    "TC10": "10] CLICKTAG OPENS STANDARD CLICK TAG PAGE",
    "TC11": "11] NO CONSOLE ERRORS IN PREVIEW (AD IFRAME)",
}
LEFT_COL_WIDTH = max(len(s) for s in CASE_LABELS.values()) + 2  # for nice alignment in mono font

# ------------------------------
# Console logger (terminal only)
# ------------------------------
def log(message: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {message}")

# ------------------------------
# Font detection (run after root)
# ------------------------------
def detect_fonts():
    global UI_FONT, TITLE_FONT, MONO_FONT
    try:
        fams = set(tkfont.families())
        def pick(candidates, fallback):
            for n in candidates:
                if n in fams:
                    return n
            return fallback
        ui = pick(["Segoe UI Variable", "Segoe UI", "Inter", "Arial"], "Segoe UI")
        mono = pick(["Cascadia Code", "Consolas", "Courier New"], "Consolas")
        UI_FONT = (ui, 10)
        TITLE_FONT = (ui, 13, "bold")
        MONO_FONT = (mono, 10)
    except Exception:
        pass

# ------------------------------
# Credentials loader
# ------------------------------
def read_credentials():
    """
    Load username/password from credentials.txt if present.
    Supported formats:
      - key=value lines (username=..., password=...)
      - or first non-empty line = username, second = password
    Env vars FT_USERNAME/FT_PASSWORD are used as fallback/defaults.
    """
    user = os.getenv("FT_USERNAME", "")
    pwd = os.getenv("FT_PASSWORD", "")

    path = Path(os.environ.get("FT_CREDENTIALS_FILE", CREDENTIALS_FILE))
    try:
        if path.is_file():
            first, second = None, None
            with path.open("r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or line.startswith("//"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip().lower()
                        v = v.strip().strip('"').strip("'")
                        if k in ("username", "user", "email", "login"):
                            user = v
                        elif k in ("password", "pass", "pwd"):
                            pwd = v
                    else:
                        if first is None:
                            first = line
                        elif second is None:
                            second = line
            if first is not None and user == "":
                user = first
            if second is not None and pwd == "":
                pwd = second
            log(f"🔐 Loaded credentials from {path}")
    except Exception as e:
        log(f"⚠️ Could not read credentials file: {e}")

    return user, pwd

# ------------------------------
# Pretty GUI log helpers
# ------------------------------
def gui_init_tags():
    """Setup text tags for colors/styles."""
    try:
        # Structure
        log_text.tag_configure("divider", foreground="#9ca3af")
        log_text.tag_configure("dim", foreground="#6b7280", font=(UI_FONT[0], 9))
        log_text.tag_configure("title", font=(UI_FONT[0], 11, "bold"))
        log_text.tag_configure("header", font=(UI_FONT[0], 10, "bold"))

        # Body text
        log_text.tag_configure("label", font=(MONO_FONT[0], 10))
        log_text.tag_configure("name", foreground="#111827", font=(UI_FONT[0], 10))
        log_text.tag_configure("url", foreground="#0369a1", font=(MONO_FONT[0], 10), underline=True)

        # Status chips
        log_text.tag_configure("chip_pass", foreground="#065f46", background="#ccfbf1",
                               font=(MONO_FONT[0], 10, "bold"))
        log_text.tag_configure("chip_fail", foreground="#991b1b", background="#fee2e2",
                               font=(MONO_FONT[0], 10, "bold"))
        log_text.tag_configure("chip_na", foreground="#4b5563", background="#f3f4f6",
                               font=(MONO_FONT[0], 10, "bold"))

        # Skip chip
        log_text.tag_configure("chip_skip", foreground="#374151", background="#e5e7eb",
                               font=(MONO_FONT[0], 10, "bold"))
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

def _clear_log():
    try:
        log_text.configure(state="normal")
        log_text.delete("1.0", "end")
        log_text.configure(state="disabled")
    except Exception:
        pass

def _gui_write_chip(value: str):
    """Write a colored chip for PASSED/FAIL/N/A."""
    v = (value or "").strip().upper()
    if v in ("PASS", "PASSED"):
        _gui_write("  PASSED  ", "chip_pass")
    elif v in ("FAIL", "FAILED"):
        _gui_write("   FAIL   ", "chip_fail")
    else:
        _gui_write("    N/A   ", "chip_na")

def _gui_write_link(url_text: str, url_href: str):
    """Insert a clickable link tag for the URL."""
    tag = f"link-{int(time.time()*1000)}"
    def _do():
        try:
            log_text.configure(state="normal")
            log_text.insert("end", url_text, (tag, "url"))
            log_text.configure(state="disabled")
            def _open(_evt, u=url_href):
                try:
                    webbrowser.open(u)
                except Exception:
                    pass
            log_text.tag_bind(tag, "<Button-1>", _open)
        except Exception:
            pass
    root.after(0, _do)

def gui_log_result(creative_id, creative_name, cases_dict, url):
    """Detailed block for processed creatives."""
    _gui_write("┄" * 84 + "\n", "divider")
    _gui_write("Creative ID: ", "header")
    _gui_write(str(creative_id or "N/A"), "title")
    if creative_name and creative_name != "[Missing]":
        _gui_write("   •   Name: ", "header")
        _gui_write(creative_name + "\n", "name")
    else:
        _gui_write("\n",)

    ordered_keys = [f"TC{i}" for i in range(1, 12)]
    for key in ordered_keys:
        label_text = CASE_LABELS.get(key, key)
        value = (cases_dict.get(key, "-") or "-")
        status_for_chip = value if value.strip() != "-" else "N/A"
        left = f"  {label_text}: "
        pad = " " * max(0, LEFT_COL_WIDTH - len(label_text))
        _gui_write(left + pad, "label")
        _gui_write_chip(status_for_chip)
        _gui_write("\n")

    if url:
        _gui_write("\nDone checking for creative <URL: ", "dim")
        _gui_write_link(url, url)
        _gui_write(">\n", "dim")
    else:
        _gui_write("\nDone checking for creative <URL: N/A>\n", "dim")
    _gui_write("┄" * 84 + "\n\n", "divider")

def gui_log_skip(creative_id, creative_name, status_text, url=None):
    """Compact block for rows skipped in QA-only mode."""
    _gui_write("┄" * 84 + "\n", "divider")
    _gui_write("Creative ID: ", "header")
    _gui_write(str(creative_id or "N/A"), "title")
    if creative_name and creative_name != "[Missing]":
        _gui_write("   •   Name: ", "header")
        _gui_write(creative_name + "\n", "name")
    else:
        _gui_write("\n",)

    _gui_write("  Status: ", "label")
    _gui_write(status_text or "N/A")
    _gui_write("\n  Result: ", "label")
    _gui_write("  NO FOR QA  ", "chip_skip")
    _gui_write(" — skipped (QA-only mode)\n")

    if url:
        _gui_write("  Link: ", "label")
        _gui_write_link(url, url)
        _gui_write("\n")
    _gui_write("┄" * 84 + "\n\n", "divider")

def focus_app_window():
    try:
        root.deiconify()
        root.lift()
        root.focus_force()
        root.attributes("-topmost", True)
        root.after(300, lambda: root.attributes("-topmost", False))
    except Exception as e:
        log(f"⚠️ Could not refocus GUI: {e}")

# ---------- Browser Bootstrap Helpers ----------
def _strip_webdrivers_from_path():
    """Remove PATH entries that contain a webdriver binary (cross-platform)."""
    try:
        names = {"chromedriver", "chromedriver.exe", "msedgedriver", "msedgedriver.exe"}
        parts = os.environ.get("PATH", "").split(os.pathsep)
        cleaned, removed = [], []
        for p in parts:
            try:
                if any(os.path.exists(os.path.join(p, n)) for n in names):
                    removed.append(p); continue
            except Exception:
                pass
            cleaned.append(p)
        if removed:
            os.environ["PATH"] = os.pathsep.join(cleaned)
            log(f"🧹 Ignoring stale webdrivers in PATH: {removed}")
    except Exception:
        pass

def _find_chrome_binary_windows():
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
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--start-maximized")
    return opts

def start_driver():
    """Start a Chrome session via Selenium Manager, fallback to Edge."""
    global driver
    if driver:
        try:
            driver.quit()
        except Exception:
            pass

    _strip_webdrivers_from_path()
    system_name = platform.system()
    log(f"🔍 Detected OS: {system_name}")

    chrome_options = _apply_common_options(ChromeOptions())
    chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})

    if system_name == "Windows":
        chrome_binary = _find_chrome_binary_windows()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            log(f"🧭 Using Chrome binary: {chrome_binary}")
        else:
            log("⚠️ Chrome binary not found in common locations/ PATH.")

    try:
        driver = webdriver.Chrome(service=ChromeService(), options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        log("✅ Chrome started successfully.")
        return
    except Exception as e:
        log(f"❌ Chrome failed to start via Selenium Manager: {e}")

    try:
        from selenium.webdriver import EdgeOptions
        from selenium.webdriver.edge.service import Service as EdgeService
        edge_options = _apply_common_options(EdgeOptions())
        edge_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        driver = webdriver.Edge(service=EdgeService(), options=edge_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        log("✅ Microsoft Edge started successfully (fallback).")
        return
    except Exception as e2:
        log(f"❌ Edge fallback failed: {e2}")

    raise RuntimeError("Unable to start a WebDriver session.")

def restart_driver(username, password, url):
    global _restart_attempts
    if _restart_attempts >= _MAX_RESTARTS:
        raise RuntimeError("Reached maximum restart attempts, aborting.")
    _restart_attempts += 1
    log(f"♻️ Restarting browser… (attempt #{_restart_attempts})")
    start_driver()
    return selenium_login(username, password, url, skip_restart=True)

# ---- Auto-close helper ----
def close_browser():
    global driver
    try:
        if driver:
            driver.quit()
            log("🔚 Browser closed.")
    except Exception as e:
        log(f"ℹ️ Could not close browser cleanly: {e}")
    finally:
        driver = None

# ---------- UX Helpers ----------
def real_chrome_zoom_out():
    try:
        pyautogui.FAILSAFE = False
        driver.maximize_window()
        log("🖥️ Browser window maximized")
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
    handles_before = set(driver.window_handles)
    preview_btn_locators = [
        (By.XPATH, XPATH_PREVIEWS_BTN_SPAN + "/ancestor::button[1]"),
        (By.XPATH, "(//button[.//span[normalize-space()='Previews']])[1]"),
        (By.XPATH, "//div[contains(@class,'toolbar') or contains(@class,'bulk') or contains(@class,'button-side')]//button[.//span[contains(normalize-space(),'Previews')]]"),
        (By.XPATH, "//button[contains(normalize-space(.), 'Previews')]"),
    ]
    menu_container_xpath = ("//nav[contains(@class,'react-contextmenu') and "
                            "(contains(@class,'is-open') or contains(@class,'react-contextmenu--visible') or @style[contains(.,'opacity: 1')])]")
    menu_item_locators = [
        (By.XPATH, XPATH_PREVIEW_CREATIVE_PRIVATE),
        (By.XPATH, menu_container_xpath + "//div[contains(@class,'react-contextmenu-item') and not(contains(@class,'disabled'))][.//span[contains(normalize-space(),'Preview Creative')]]"),
        (By.XPATH, "//span[contains(normalize-space(),'Preview Creative')]"),
    ]
    previews_clicked = False
    for _ in range(3):
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
    largest, largest_area = None, -1
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
    reset_zoom(); time.sleep(0.2)
    handles_before = set(driver.window_handles)
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
        try:
            anchor = WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/clicktag']"))
            )
        except TimeoutException:
            anchors = driver.find_elements(By.CSS_SELECTOR, "a[target='_blank'], a[href]")
            if not anchors:
                raise TimeoutException("No anchor elements found in preview")
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
    click_handle = [h for h in driver.window_handles if h not in handles_before]
    click_handle = click_handle[-1] if click_handle else None
    if click_handle:
        driver.switch_to.window(click_handle)
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
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
    allowed_patterns = []
    try:
        frame = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#ad"))
        )
        src = (frame.get_attribute("src") or "").strip()
        if src:
            u = urlparse(src)
            allowed_patterns = [f"{u.scheme}://{u.netloc}/lcrp/", u.netloc]
    except Exception:
        return False, []
    ignore_substrings = [
        "/crm/v1/user", "/int/v1/ui/creative-libraries", "grafana/faro-web-sdk",
        "Problem Starting up Pendo", "DEPRECATED_ENDPOINT", "SharedImageManager::ProduceMemory",
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
    """Navigate, login, scan grid, run checks."""
    global driver, SUMMARY_PREFIX
    try:
        if not skip_restart:
            start_driver()
        log(f"🌐 Navigating to URL: {url}")
        driver.get(url)

        qa_only = not PROCESS_ALL
        processed_count = 0
        expected_total = 0

        # --- Login ---
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.NAME, "username"))
            ).send_keys(username)
            driver.find_element(By.NAME, "password").send_keys(password)
            driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)
            log(f"🔐 Login attempted for user: {username}")

            WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".react-grid-Row"))
            )

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
                driver.execute_script("arguments[0].scrollLeft = arguments[0].scrollWidth", scrollable_div)
                time.sleep(0.5)
                log("📜 All rows loaded and columns revealed.")
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

        # Fetch rows and compute expected count based on mode
        rows = driver.find_elements(By.CSS_SELECTOR, "div.react-grid-Row")

        def status_of(row):
            try:
                cells = row.find_elements(By.CSS_SELECTOR, ".react-grid-Cell")
                return cells[col_index_map.get("status", 0)].text.strip()
            except Exception:
                return ""

        if qa_only:
            expected_total = sum(1 for r in rows if "qa" in status_of(r).lower())
            SUMMARY_PREFIX = "For QA creatives processed: "
        else:
            expected_total = len(rows)
            SUMMARY_PREFIX = "Creatives processed: "
        _set_summary(processed_count, expected_total)

        # Console header
        log("\n🧪 Results Table")
        log(f"{'Creative Name':50} {'ID':10} {'Status':12} {'TC1':8} {'TC2':20} {'TC3':15} {'TC4':20} {'TC5':20} {'TC6':15} {'TC7':30} {'TC8':30} {'TC9':20} {'TC10':10} {'TC11':10}")
        log("-" * 290)

        # Iterate
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
                is_for_qa = "for qa" in status_text.lower() or status_text.strip().lower() == "qa"

                # If QA-only mode and not FOR QA → skip with compact note
                if qa_only and not is_for_qa:
                    gui_log_skip(creative_id, creative_name, status_text, creative_url or None)
                    continue

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

                # --- TEST CASES ---
                test_case_1 = "PASSED" if is_for_qa else "FAIL"

                placement_required_types = ["alt image", "html_onpage", "html_expand", "html_standard"]
                if placement_size != "0x0" and creative_type.lower() in placement_required_types:
                    test_case_2 = "PASSED" if placement_size in creative_name.replace(" ", "") else "FAIL"
                else:
                    test_case_2 = "PASSED"

                valid_formats = [".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4"]
                test_case_3 = "PASSED" if any(creative_name.lower().endswith(fmt) for fmt in valid_formats) else "FAIL"

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

                test_case_6 = "PASSED" if placement_size.lower() == "1x1" else "N/A"

                try:
                    file_name_col = cells[col_index_map["file name"]].text.strip() if "file name" in col_index_map else ""
                    test_case_7 = "PASSED" if creative_name.lower() == file_name_col.lower() else "FAIL"
                except Exception:
                    test_case_7 = "FAIL"

                if ctype in ["preroll", "vastaudio"]:
                    duration_values = ["6", "10", "15", "20", "30", "60", "90", "120"]
                    aspect_ratios = ["16x9", "4x3", "1x1", "9x16"]
                    has_duration = any(dur in creative_lower for dur in duration_values)
                    has_ratio = any(ratio in creative_lower for ratio in aspect_ratios)
                    test_case_8 = "PASSED" if (has_duration and has_ratio) else "FAIL"
                else:
                    test_case_8 = "N/A"

                if creative_lower.endswith(".mp3"):
                    test_case_9 = "PASSED" if ctype == "vastaudio" else "FAIL"
                else:
                    test_case_9 = "N/A"

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
                            tc11_status = "FAIL" if has_errors else "PASSED"
                            if has_errors:
                                log("❌ TC11 console errors detected:")
                                for e in errs[:10]:
                                    log("    " + e[:500])
                            else:
                                log("✅ TC11: No console errors detected in Preview.")
                            detected, click_handle = _click_creative_in_preview()
                            tc10_status = "PASSED" if detected else "FAIL"
                            log(f"TC10 ClickTag: {tc10_status}")
                        except Exception as e:
                            log(f"⚠️ TC10/11 preview flow error: {e}")
                        finally:
                            try:
                                if click_handle and click_handle in driver.window_handles:
                                    driver.switch_to.window(click_handle); driver.close()
                            except Exception:
                                pass
                            try:
                                if preview_handle and preview_handle in driver.window_handles:
                                    driver.switch_to.window(preview_handle); driver.close()
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

                # processed count (either all rows, or only QA rows)
                processed_count += 1
                _set_summary(processed_count, expected_total)

                # Console row
                log(f"{creative_name:50} {creative_id:10} {status_text:12} {test_case_1:8} {test_case_2:20} {test_case_3:15} {test_case_4:20} {test_case_5:20} {test_case_6:15} {test_case_7:30} {test_case_8:30} {test_case_9:20} {tc10_status:10} {tc11_status:10}")

                # GUI full row
                cases = {
                    "TC1":  test_case_1, "TC2":  test_case_2, "TC3":  test_case_3,
                    "TC4":  test_case_4, "TC5":  test_case_5, "TC6":  test_case_6,
                    "TC7":  test_case_7, "TC8":  test_case_8, "TC9":  test_case_9,
                    "TC10": tc10_status, "TC11": tc11_status,
                }
                gui_log_result(creative_id, creative_name, cases, last_checked_url)

            except Exception as e:
                log(f"{'[Missing]':100} {'[Missing]':15} {'[Error]':20} {'FAIL':15} {'Could not extract':25} {'FAIL':20} {'FAIL':20} {'FAIL':25} {'FAIL':30} {'FAIL':30} {'FAIL':30} {'FAIL':30} {'-':10} {'-':10}")
                log(f"⚠️ Row {idx+1} failed: {e}")

        # Done → close browser
        log(f"🎉 Finished. {SUMMARY_PREFIX}{processed_count}/{expected_total}. Closing browser…")
        close_browser()

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

# --- summary label updater (thread-safe) ---
def _set_summary(processed: int, expected: int):
    try:
        root.after(0, lambda: summary_var.set(f"{SUMMARY_PREFIX}{processed} / {expected}"))
    except Exception:
        pass

# ---------- GUI ----------
def submit():
    global PROCESS_ALL, SUMMARY_PREFIX
    username = entry_username.get().strip()
    password = entry_password.get().strip()
    url = entry_url.get().strip()
    PROCESS_ALL = bool(check_all_var.get())
    SUMMARY_PREFIX = "Creatives processed: " if PROCESS_ALL else "For QA creatives processed: "

    if not username or not password or not url:
        messagebox.showwarning("Input Error", "Please fill in all fields.")
        return

    # Clear display if requested
    if bool(clear_display_var.get()):
        _clear_log()
        _gui_write("✨ Results will be summarized here as each creative is processed.\n\n", "dim")

    # reset summary at start
    _set_summary(0, 0)

    t = threading.Thread(target=selenium_login, args=(username, password, url), daemon=True)
    t.start()

# --- GUI Setup ---
root = tk.Tk()
root.title("Basefile QA - East Coast")
root.geometry("1080x720")
root.resizable(False, True)

# Detect best fonts available on this machine
detect_fonts()

# Title bar
title_frame = tk.Frame(root)
title_frame.pack(fill="x", pady=(10, 0))
title_label = tk.Label(title_frame, text="Basefile QA — East Coast", font=TITLE_FONT)
title_label.pack()

# ---- Centered form (does not expand full width) ----
form_wrapper = tk.Frame(root)
form_wrapper.pack(pady=10)

content = tk.LabelFrame(form_wrapper, text="Sign In & Target", font=(UI_FONT[0], 10, "bold"), padx=12, pady=10)
content.pack()

tk.Label(content, text="Username:", font=UI_FONT).grid(row=0, column=0, sticky="e", padx=8, pady=6)
entry_username = tk.Entry(content, width=40, font=UI_FONT)
entry_username.grid(row=0, column=1, padx=8, pady=6)

tk.Label(content, text="Password:", font=UI_FONT).grid(row=1, column=0, sticky="e", padx=8, pady=6)
entry_password = tk.Entry(content, show="*", width=40, font=UI_FONT)
entry_password.grid(row=1, column=1, padx=8, pady=6)

tk.Label(content, text="URL:", font=UI_FONT).grid(row=2, column=0, sticky="e", padx=8, pady=6)
entry_url = tk.Entry(content, width=60, font=UI_FONT)
entry_url.grid(row=2, column=1, padx=8, pady=6)

# Checkbox: Check all (uncheck = QA only)
check_all_var = tk.BooleanVar(value=False)
check_all_cb = tk.Checkbutton(content, text="Check all? (uncheck = QA only)", variable=check_all_var, onvalue=True, offvalue=False, font=UI_FONT)
check_all_cb.grid(row=3, column=0, columnspan=2, pady=(6, 2))

# Checkbox: Clear display each run
clear_display_var = tk.BooleanVar(value=True)
clear_cb = tk.Checkbutton(content, text="Clear display (on each run)", variable=clear_display_var, onvalue=True, offvalue=False, font=UI_FONT)
clear_cb.grid(row=4, column=0, columnspan=2, pady=(0, 6))

# Prefill from env/credentials
_loaded_user, _loaded_pass = read_credentials()
entry_username.insert(0, os.getenv("FT_USERNAME", _loaded_user))
entry_password.insert(0, os.getenv("FT_PASSWORD", _loaded_pass))
entry_url.insert(0, os.getenv("FT_URL", ""))

# centered Run button
run_btn = tk.Button(content, text="Run", command=submit, font=(UI_FONT[0], 10, "bold"))
run_btn.grid(row=5, column=0, columnspan=2, pady=10)

# Pretty Log display (bottom)
log_group = tk.LabelFrame(root, text="Execution Report", font=(UI_FONT[0], 10, "bold"))
log_group.pack(fill="both", expand=True, padx=12, pady=(0, 12))

# Summary label at the top of results
summary_var = tk.StringVar(value="For QA creatives processed: 0 / 0")
summary_frame = tk.Frame(log_group)
summary_frame.pack(fill="x", padx=10, pady=(8, 0))
summary_label = tk.Label(summary_frame, textvariable=summary_var, anchor="w", font=(UI_FONT[0], 10, "bold"))
summary_label.pack(side="left")

log_text = scrolledtext.ScrolledText(log_group, state="disabled", wrap="word", font=MONO_FONT)
log_text.pack(fill="both", expand=True, padx=10, pady=10)
gui_init_tags()
_gui_write("✨ Results will be summarized here as each creative is processed.\n\n", "dim")

root.mainloop()