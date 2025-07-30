import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import threading
import time

# --- Selenium login function ---
def selenium_login(username, password, url, region):
    try:
        driver = webdriver.Chrome()
        driver.get(url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)

        print(f"🔐 Login attempted for region: {region}")

        # Wait for status labels to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".status-label"))
        )

        # Get all QA status elements
        qa_elements = driver.find_elements(By.CSS_SELECTOR, ".status-label.in-qa")
        print(f"✅ Total QA rows found: {len(qa_elements)}")

        # Click checkboxes for each QA row
        for status_el in qa_elements:
            try:
                # Traverse DOM to get to the checkbox row
                row_el = status_el.find_element(By.XPATH, "./ancestor::div[contains(@class, 'react-grid-Row')]")

                # Click the label/span instead of the <input>
                label = row_el.find_element(By.CSS_SELECTOR, 'label.select-holder')
                driver.execute_script("arguments[0].scrollIntoView(true);", label)
                ActionChains(driver).move_to_element(label).click().perform()

                print("☑️ Ticked checkbox for QA row")
            except Exception as e:
                print(f"⚠️ Could not tick checkbox for one QA row: {e}")

    except Exception as e:
        print("❌ Error:", e)

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
root.title("Basefile QA")
root.geometry("400x300")
root.resizable(False, False)

# Center content using a frame
content = tk.Frame(root)
content.place(relx=0.5, rely=0.5, anchor="center")

# Username
tk.Label(content, text="Username:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
entry_username = tk.Entry(content, width=30)
entry_username.grid(row=0, column=1, padx=5, pady=5)

# Password
tk.Label(content, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
entry_password = tk.Entry(content, show="*", width=30)
entry_password.grid(row=1, column=1, padx=5, pady=5)

# URL
tk.Label(content, text="URL:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
entry_url = tk.Entry(content, width=30)
entry_url.grid(row=2, column=1, padx=5, pady=5)

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
