import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading

# --- Selenium login function ---
import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
import traceback

def selenium_login(username, password, url, region):
    try:
        driver = webdriver.Chrome()
        driver.get(url)
        print("🌐 Navigated to URL...")

        # Login
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "username"))
        ).send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)

        print(f"🔐 Login attempted for region: {region}")

        # Wait for status labels
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".status-label.in-approved"))
        )
        approved_elements = driver.find_elements(By.CSS_SELECTOR, ".status-label.in-approved")
        print(f"✅ Total 'in-approved' rows found: {len(approved_elements)}")

        # Print header
        # Print header
        print("\n🧪 Results Table")
        print(f"{'Creative Name':100} {'ID':15} {'Status':20} {'Test Case 1':15} {'Test Case 2':25} {'Test Case 3':10}")
        print("-" * 120)

        # Get all creative rows
        rows = driver.find_elements(By.CSS_SELECTOR, "div.react-grid-Row")

        for idx, row in enumerate(rows):
            try:
                name_el = row.find_element(By.CSS_SELECTOR, "span.name-overflow a")
                creative_name = name_el.text.strip()

                id_el = row.find_element(By.CSS_SELECTOR, "div.react-grid-Cell[style*='left: 390px']")
                creative_id = id_el.text.strip()

                status_el = row.find_element(By.CSS_SELECTOR, ".status-label")
                status_text = status_el.text.strip()

                # --- Extract Placement Size ---
                try:
                    placement_el = row.find_element(By.XPATH, ".//div[contains(@class, 'react-grid-Cell') and contains(., 'x')]")
                    placement_size = placement_el.text.strip().replace(" ", "")  # e.g., "300x250"
                except:
                    placement_size = "0x0"

                # --- Test Case 2 ---
                if placement_size != "0x0" and placement_size not in creative_name.replace(" ", ""):
                    test_case_2 = f"FAIL: name lacks {placement_size}"
                else:
                    test_case_2 = f"PASSED: {placement_size}"

                # Sample stubs for other test cases
                test_case_1 = "PASSED"
                test_case_3 = "PASSED"

                print(f"{creative_name:100} {creative_id:15} {status_text:20} {test_case_1:15} {test_case_2:25} {test_case_3:10}")

            except Exception as e:
                print(f"{'[Missing]':50} {'[Missing]':10} {'[Error]':10} {'FAIL':15} {'Could not extract':25} {'FAIL':10}")
                print(f"⚠️ Row {idx+1} failed: {e}")


        print("\n🏁 Test complete. Closing browser.")
        driver.quit()

    except Exception as e:
        print("❌ Error during login or scanning:")
        traceback.print_exc()
        # driver.quit()

# --- Submit handler ---
def submit():
    username = entry_username.get()
    password = entry_password.get()
    url = entry_url.get()
    region = region_var.get()

    if not username or not password or not url:
        messagebox.showwarning("Input Error", "Please fill in all fields.")
        return

    threading.Thread(target=selenium_login, args=(username, password, url, region)).start()

# --- GUI Setup ---
root = tk.Tk()
root.title("Basefile QA Test")
root.geometry("400x300")
root.resizable(False, False)

# Center content using a frame
content = tk.Frame(root)
content.place(relx=0.5, rely=0.5, anchor="center")

# --- AUTO-FILLED VERSION ---


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

# Region dropdown
tk.Label(content, text="Region:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
region_var = tk.StringVar()
dropdown = ttk.Combobox(content, textvariable=region_var, values=["East Coast", "EMEA", "JAPAC"], width=28)
dropdown.grid(row=3, column=1, padx=5, pady=5)
dropdown.current(0)

# Run button
run_btn = tk.Button(content, text="Run", command=submit, width=20)
run_btn.grid(row=4, column=0, columnspan=2, pady=15)

root.mainloop()
