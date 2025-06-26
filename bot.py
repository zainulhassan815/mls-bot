from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc

import time
import requests
import re
import base64
import json
from urllib.parse import urlparse, parse_qs, unquote

from flask import Flask, request

import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

load_dotenv()
IS_DEV_MODE = os.environ.get("ENVIRONMENT") != "PROD"
PODIO_API_URL = os.environ.get("PODIO_API_URL")

app = Flask(__name__)
driver = None

if not os.path.exists("logs"):
    os.mkdir("logs")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

info_handler = RotatingFileHandler("logs/info.log", maxBytes=1000000, backupCount=3)
info_handler.setLevel(logging.INFO)
info_format = logging.Formatter(
    "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)
info_handler.setFormatter(info_format)

error_handler = RotatingFileHandler("logs/error.log", maxBytes=1000000, backupCount=3)
error_handler.setLevel(logging.ERROR)
error_format = logging.Formatter(
    "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)
error_handler.setFormatter(error_format)


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO


class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.ERROR


info_handler.addFilter(InfoFilter())
error_handler.addFilter(ErrorFilter())

logger.addHandler(info_handler)
logger.addHandler(error_handler)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(info_format)
logger.addHandler(stream_handler)


def save_screenshot(driver, label):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"logs/screenshot_{label}_{timestamp}.png"
    try:
        os.makedirs("logs", exist_ok=True)
        driver.save_screenshot(filename)
        print(f"Screenshot saved: {filename}")
    except Exception as e:
        print(f"Failed to save screenshot: {e}")


def scrap():
    element = WebDriverWait(driver, 40).until(
        EC.visibility_of_element_located((By.ID, "_ctl0_m_pnlRenderedDisplay"))
    )

    logger.info("Waiting for 10 sec")
    time.sleep(10)

    logger.info("-------- Addresses and Prices --------")
    tr_nodes = driver.find_elements(By.XPATH, '//tr[contains(@class, "d693m10")]')
    address_price_array = []
    for tr_node in tr_nodes:

        first_td = tr_node.find_elements(By.XPATH, ".//td[1]")[0]
        last_td = tr_node.find_elements(By.XPATH, ".//td[last()]")[0]
        address = first_td.text.strip()
        price = last_td.text.strip()
        address_price_array.append(
            {
                "address": address,
                "price": price,
            }
        )

    logger.info(f"Address and price data: {address_price_array}")

    logger.info("-------- MLS, Beds, TaxAmount, ListAgents, DOM/CDOM --------")
    elements = driver.find_elements(
        By.XPATH, "//*[contains(concat(' ', normalize-space(@class), ' '), ' d678m0 ')]"
    )
    property_data = []

    for element in elements:
        node_value = element.text
        mls_matches = re.search(r"MLS #:\s*(\S+)", node_value)
        beds_matches = re.search(r"Beds:\s*(\d+)", node_value)
        baths_matches = re.search(r"Baths:\s*((\d+(\s*\/\s*\d+)?)|\d+)", node_value)
        list_agent_matches = re.search(r"List Agent:\s*(.*)", node_value)
        dom_cdom_matches = re.search(r"DOM\/CDOM:\s*(\d+\s*\/\s*\d+)", node_value)
        tax_position = node_value.find("Tax Annual Amt")
        tax_info = node_value[tax_position + len("Tax Annual Amt") :].strip()
        tax_values = re.search(r"\$\s*([\d,]+)\s*\/\s*(\d+)", tax_info)
        property_info = {
            "MLS": mls_matches.group(1) if mls_matches else "",
            "Beds": beds_matches.group(1) if beds_matches else "",
            "Baths": baths_matches.group(1) if baths_matches else "",
            "List Agent": list_agent_matches.group(1) if list_agent_matches else "",
            "DOM/CDOM": dom_cdom_matches.group(1) if dom_cdom_matches else "",
            "Tax Annual Amt / Year": (
                f"${tax_values.group(1)} / {tax_values.group(2)}" if tax_values else ""
            ),
        }
        property_data.append(property_info)

    logger.info(f"Property data: {property_data}")

    logger.info("-------- Email --------")
    a_elements = driver.find_elements(By.XPATH, '//td[@class="d115m13"]//a')
    emails = []
    for a_element in a_elements:
        href = a_element.get_attribute("href")
        url_components = urlparse(href)
        if url_components.query:
            query_parameters = parse_qs(url_components.query)
            if "laemail" in query_parameters:
                email = unquote(query_parameters["laemail"][0])
                emails.append(email)
        if url_components.fragment:
            fragment_parameters = parse_qs(url_components.fragment)
            if "laemail" in fragment_parameters:
                email = unquote(fragment_parameters["laemail"][0])
                emails.append(email)

    logger.info(f"Emails: {emails}")

    logger.info("-------- Combined arrays --------")
    encoded_ascii = ""
    if address_price_array and emails and property_data:
        combined_array = []
        for key, value in enumerate(address_price_array):
            combined_array.append({**value, **property_data[key], "email": emails[key]})
        logger.info(f"Combined arrays data: {combined_array}")
        json_string = json.dumps(combined_array, ensure_ascii=False)
        encoded_bytes = base64.b64encode(json_string.encode("utf-8"))
        encoded_ascii = encoded_bytes.decode("ascii")

    headers = {"Content-Type": "application/json"}

    data = {"data": encoded_ascii}
    try:
        response = requests.post(PODIO_API_URL, json=data, headers=headers)

        if response.status_code == 200:
            logger.info(f"Request successful. Response content: {response.json()}")
        else:
            logger.info(f"Request failed with status code: {response.status_code}")
            logger.info(f"Response content: {response.text}")

    except Exception as e:
        logger.error(f"Exception occurred: {e}", exc_info=True)
        save_screenshot(driver, "exception_occurred_podio_post")


def alert():
    try:
        alert = driver.switch_to.alert
        alert.save()
        logger.info("Password save dialogue dismissed.")
    except:
        # If no alert is present, continue with other actions
        logger.info("No password save dialogue found.")


def remove_google_ad():
    try:
        if driver.find_elements(By.ID, "modal-container"):
            deleteableelements = driver.find_elements(By.ID, "modal-container")
            for element in deleteableelements:
                driver.execute_script(
                    """var element = arguments[0]; element.parentNode.removeChild(element);""",
                    element,
                )
                logger.info("Element Deleted")
    except Exception:
        logger.info("Off")
        save_screenshot(driver, "exception_occurred_remove_google_ad")


def run_script(postlogin, postpassword, desired_buttons):
    global driver  # Use the global variable
    options = uc.ChromeOptions()

    options.add_argument("--incognito" if IS_DEV_MODE else "--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")

    # -----------------------------Define the options for the browser-------------
    driver = uc.Chrome(options=options)
    driver.set_window_size(1920, 1080)

    # -----------------------------Website Url Bright MLS-------------
    url = "https://login.brightmls.com/login"
    driver.get(url)
    save_screenshot(driver, "login_page_loaded")

    # -----------------------credentials----------------------------
    logger.info(f"Desired buttons: {desired_buttons}")
    login = postlogin
    password = postpassword
    logger.info(f"login: {postlogin}, password: {postpassword}")

    # -------------------------Enter Login details-------------
    logger.info("1. Enter login details")
    wait = WebDriverWait(driver, 30)
    input_element = wait.until(
        expected_conditions.visibility_of_element_located((By.ID, "username"))
    )
    input_element.clear()
    input_text = str(login)
    input_element.send_keys(input_text)
    save_screenshot(driver, "username_entered")

    # -------------------------Enter password details-------------
    logger.info("2. Enter password details")
    wait = WebDriverWait(driver, 30)
    input_element = wait.until(
        expected_conditions.visibility_of_element_located((By.ID, "password"))
    )
    input_element.clear()
    input_text = str(password)
    input_element.send_keys(input_text)
    save_screenshot(driver, "password_entered")

    try:
        # -------------------------Click on Login Button -------------
        wait = WebDriverWait(driver, 5)
        button = wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    ".MuiButtonBase-root.MuiButton-root.jss44.MuiButton-contained.MuiButton-containedPrimary",
                )
            )
        )
        button.click()
        save_screenshot(driver, "after_login_click")

        # -------------------------Apply check after login(Dashboard open or Not) -------------
    except Exception as e:
        logger.error(f"Exception occurred: {e}", exc_info=True)
        input_element.send_keys(Keys.ENTER)
        save_screenshot(driver, "after_login_click")

    wait = WebDriverWait(driver, 180)
    button = wait.until(
        expected_conditions.visibility_of_element_located(
            (By.CLASS_NAME, "app-children-container")
        )
    )
    save_screenshot(driver, "dashboard_loaded")

    # -------------------------Click on Clients Popup Menu-------------
    time.sleep(10)
    remove_google_ad()

    try:
        wait = WebDriverWait(driver, 65)
        element = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="Clients"]'))
        )
        element.click()
        save_screenshot(driver, "clients_clicked")
    except Exception as e:
        save_screenshot(driver, "exception_occurred_clients_click")
        wait = WebDriverWait(driver, 20)
        element = driver.find_element(By.CSS_SELECTOR, '[aria-label="Clients"]')
        element.click()
        save_screenshot(driver, "clients_clicked")

    # -------------------------Click on Clients Popup Menu-------------
    time.sleep(10)
    try:
        wait = WebDriverWait(driver, 20)
        element = wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Auto Email (New)"))
        )
        element.click()
        save_screenshot(driver, "auto_email_clicked")

    except:
        wait = WebDriverWait(driver, 20)
        element = driver.find_element(By.CSS_SELECTOR, '[aria-label="Clients"]')
        element.click()
        wait = WebDriverWait(driver, 20)
        element = wait.until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Auto Email (New)"))
        )
        element.click()
        save_screenshot(driver, "auto_email_clicked")
        time.sleep(15)

    def click_accordion_button(desired_buttons):

        accordion_items = driver.find_elements(By.CLASS_NAME, "accordion-item")

        for item in accordion_items:
            accordion_button = item.find_element(By.CLASS_NAME, "accordion-button")
            button_text = accordion_button.text.strip()

            if button_text in desired_buttons:
                logger.info(f"Clicking the button with text: {button_text}")
                accordion_button.click()
                save_screenshot(driver, "accordion_button_clicked")
                time.sleep(3)

                try:
                    open_in_portal_button = item.find_elements(By.TAG_NAME, "a")
                    open_in_portal_button[5].click()
                    time.sleep(7)  # Adjust the sleep duration as needed
                    # Switch to the new tab
                    driver.switch_to.window(driver.window_handles[1])
                    save_screenshot(driver, "before_scraping")

                    try:
                        scrap()
                        driver.switch_to.window(driver.window_handles[0])
                    except:
                        scrap()

                    save_screenshot(driver, "after_scraping")

                except Exception as e:
                    save_screenshot(driver, "exception_occurred_scraping")
                    logger.error(f"Exception occurred: {e}", exc_info=True)
                    headers = {"Content-Type": "application/json"}

                    data = {"data": "Open in portal button not found"}
                    driver.quit()
                    try:
                        response = requests.post(
                            PODIO_API_URL, json=data, headers=headers
                        )

                        if response.status_code == 200:
                            logger.info(
                                f"Request successful. Response content: {response.text}"
                            )
                        else:
                            logger.info(
                                f"Request failed with status code: {response.status_code}"
                            )
                            logger.info("Response content:", response)

                    except Exception as e:
                        logger.error(f"Exception occurred: {e}", exc_info=True)

    click_accordion_button(desired_buttons)
    logger.info("Program END")
    time.sleep(3)


@app.route("/index", methods=["POST"])
def index():
    if request.method == "POST":
        agent_list = []
        try:
            agents = request.form.get("agents")
            if agents:
                agent_list = agents.split(" | ")

            run_script(
                request.form.get("login"), request.form.get("password"), agent_list
            )
        except Exception as e:
            logger.error(
                f"Running run_script again. Exception occurred: {e}", exc_info=True
            )
            run_script(
                request.form.get("login"), request.form.get("password"), agent_list
            )
        finally:
            driver.quit()

        return {"status": 200, "message": "Execution Successful"}
    else:
        return {"status": 400, "message": "Bad Request"}


if __name__ == "__main__":
    if IS_DEV_MODE:
        app.run(host="0.0.0.0", port=5000, debug=True)
    else:
        from waitress import serve

        serve(app, host="0.0.0.0", port=5000)
