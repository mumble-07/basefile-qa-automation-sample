# Basefile QA Automation

## Overview

This project automates the QA process for creatives using a GUI application built with Python, Selenium, and Tkinter. It logs into a web platform, scans a grid of creatives, and runs a series of checks to ensure compliance with QA standards. Results are displayed in a user-friendly GUI and logged to the console.

## Features
- **GUI Application**: User-friendly interface for entering credentials and target URL.
- **Automated Browser Control**: Uses Selenium to interact with Chrome/Edge and perform checks.
- **Comprehensive QA Checks**: 11 test cases covering creative status, naming, file types, sizes, and more.
- **Detailed Logging**: Results are shown in a styled GUI log and printed to the console.
- **Flexible Credential Loading**: Supports multiple locations and formats for credentials.
- **Zoom/UX Helpers**: Ensures browser zoom and grid visibility for robust automation.

## File Structure
- `script_v4.py`: Main automation script.
- `credentials.txt`: Stores username and password for login.

## How to Use
1. **Install Requirements**:
   - Python 3.x
   - Selenium
   - PyAutoGUI
   - Tkinter (usually included with Python)

   # Basefile QA Automation

   ## Overview

   Basefile QA Automation is a Python-based GUI tool for automating the quality assurance (QA) of digital creatives. It uses Selenium to control a browser, Tkinter for the GUI, and PyAutoGUI for OS-level interactions. The tool logs into a web platform, scans a grid of creatives, and runs a series of checks to ensure compliance with QA standards. Results are displayed in a styled GUI and printed to the console.

   ## Features
   - **Intuitive GUI**: Enter credentials, target URL, and select QA mode.
   - **Automated Browser Control**: Selenium manages Chrome/Edge for robust automation.
   - **Comprehensive QA Checks**: 11 test cases for creative status, naming, file types, sizes, and more.
   - **Detailed Logging**: Styled GUI log and console output for all results.
   - **Flexible Credential Loading**: Supports multiple locations and formats for credentials.
   - **Zoom/UX Helpers**: Ensures browser zoom and grid visibility for reliable automation.

   ## File Structure
   - `script_v4.py`: Main automation script.
   - `credentials.txt`: Stores username and password for login.

   ## Setup & Usage
   1. **Install Requirements**:
       - Python 3.x
       - Selenium (`pip install selenium`)
       - PyAutoGUI (`pip install pyautogui`)
       - Tkinter (usually included with Python)
   2. **Prepare `credentials.txt`**:
       - Format: `username=your_email` (first line), `password=your_password` (second line or as key-value)
   3. **Run the Script**:
       - Execute `python3 script_v4.py` or use the provided executable.
   4. **Fill in the GUI**:
       - Enter your username, password, and target URL.
       - Choose QA-only or all creatives.
       - Click "Run" to start automation.

   ## Architecture & Main Functions

   ### Credential Management
   - **`read_credentials()`**: Loads credentials from environment variables or various file locations. Supports both key-value and line-based formats. Calls `_candidate_credential_paths()` to find possible locations and `_parse_credentials_file()` to extract username/password.
      - **Parameters**: None
      - **Returns**: `(username, password)` tuple

   ### GUI Setup & Helpers
   - **Tkinter GUI**: Provides fields for username, password, URL, and options for QA mode and display clearing.
   - **`detect_fonts()`**: Detects and sets the best available fonts for the GUI.
   - **`gui_init_tags()`**: Styles the log output for clarity (colors, fonts, chips).
   - **`_gui_write(text, *tags)`**: Writes styled text to the GUI log.
   - **`_gui_write_chip(value)`**: Writes a colored status chip (PASS/FAIL/SKIP/N/A) to the log.
   - **`_gui_write_link(url_text, url_href)`**: Inserts a clickable link in the log.
   - **`_clear_log()`**: Clears the log display.
   - **`focus_app_window()`**: Brings the GUI window to the front.

   ### Selenium Browser Automation
   - **`start_driver()`**: Starts a Chrome (or Edge) browser session with required options. Handles OS detection and browser binary location.
      - **Parameters**: None
      - **Returns**: None (sets global `driver`)
   - **`restart_driver(username, password, url)`**: Handles browser restarts on failure.
      - **Parameters**: `username`, `password`, `url`
      - **Returns**: Calls `selenium_login()`
   - **`close_browser()`**: Closes the browser session cleanly.
      - **Parameters**: None
      - **Returns**: None

   ### Zoom & UX Helpers
   - **`reset_zoom()`**: Restores browser zoom to 100% using OS-level shortcuts.
   - **`zoom_to(percent)`**: Sets browser zoom to a preset percentage (e.g., 80%).
   - **`real_chrome_zoom_out()`**: Aggressively zooms out for grid view (~25%).

   ### Creative Grid Processing & QA Checks
   - **`selenium_login(username, password, url, skip_restart=False)`**: Main function. Logs in, loads the grid, iterates through creatives, and runs all QA checks. Handles scrolling, zoom, and row selection.
      - **Parameters**: `username`, `password`, `url`, `skip_restart` (default False)
      - **Returns**: None
      - **Process**:
         1. Logs in using credentials.
         2. Loads all grid rows and columns.
         3. Iterates through creatives, running 11 test cases:
             - **TC1**: Status is "FOR QA"
             - **TC2**: Name contains placement size
             - **TC3**: Name contains file format suffix
             - **TC4**: Type matches file extension
             - **TC5**: File size ≤ 600KB (except preroll/vastaudio)
             - **TC6**: 1x1 placement auto-approve
             - **TC7**: Name matches file name column
             - **TC8**: Preroll/vastaudio file name has duration & aspect ratio
             - **TC9**: MP3 must be vastaudio type
             - **TC10**: Clicktag opens correct page
             - **TC11**: No console errors in preview
         4. Logs results in GUI and console.
         5. Handles browser zoom and tab management for previews.

   ### Logging & Reporting
   - **`gui_log_result(creative_id, creative_name, cases_dict, url, note=None)`**: Displays detailed results for each creative in the GUI.
      - **Parameters**: `creative_id`, `creative_name`, `cases_dict` (dict of TC results), `url`, `note` (optional)
   - **`gui_log_skip(creative_id, creative_name, status_text, url=None)`**: Logs skipped creatives in QA-only mode.
      - **Parameters**: `creative_id`, `creative_name`, `status_text`, `url` (optional)
   - **Console Logging**: All actions and results are also printed to the terminal using `log()`.

   ### Utility Functions
   - **Font detection**: Picks best available fonts for GUI (`detect_fonts`).
   - **Checkbox/row selection**: Robust helpers for interacting with grid rows (`_click_checkbox_in_row`, `_safe_click`).
   - **Preview/clicktag helpers**: Opens previews, checks clicktag functionality, and reads browser console errors (`_open_preview_for_selected`, `_click_creative_in_preview`, `_check_preview_console_errors`).
   - **Other helpers**: Scrolling, searching, and extracting cell text for robust grid interaction.

   ## Customization
   - **Test Case Labels**: Easily update `CASE_LABELS` for new or changed QA requirements.
   - **XPaths**: Update `XPATH_PREVIEWS_BTN_SPAN` and `XPATH_PREVIEW_CREATIVE_PRIVATE` for platform changes.

   ## Security
   - Credentials are loaded securely and can be overridden by environment variables.
   - Passwords are not displayed in the GUI.

   ## Troubleshooting
   - If browser fails to start, ensure Chrome/Edge is installed and accessible.
   - If credentials are not found, check all supported locations and formats.
   - For grid/preview issues, verify XPaths and selectors match the target platform.
   - For PyAutoGUI errors, ensure accessibility permissions are granted (especially on macOS).

   ## License
   This project is provided as-is for internal automation and QA purposes.
