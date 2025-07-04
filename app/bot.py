from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc

import time
import requests
import re
import base64
import json

from typing import Callable

from flask import Flask, request, g

import os

from screenshot import create_screenshot_dir, save_screenshot, cleanup_old_screenshots
from log_setup import setup_logger

logger = setup_logger()

from dotenv import load_dotenv

load_dotenv()
IS_DEV_MODE = os.environ.get("ENVIRONMENT") != "PROD"

app = Flask(__name__)


def scrap(driver: WebDriver) -> str:
    """Scrap data from listing page."""

    logger.info("Waiting for listings to load")
    WebDriverWait(driver, 40).until(
        EC.visibility_of_element_located((By.ID, "_ctl0_m_pnlRenderedDisplay"))
    )
    logger.info("Listings loaded. Waiting for 10 sec")
    time.sleep(10)

    original_window = driver.current_window_handle

    # Find all listing tables
    data = []
    tables = driver.find_elements(
        By.XPATH, '//td[@class="d693m1"]/table[@class="d693m2"]'
    )
    for table in tables:
        table.location_once_scrolled_into_view
        listing_item = {}

        try:
            # Address and price data
            address_and_price_row = table.find_element(By.CSS_SELECTOR, "tr.d693m10")
            listing_item["address"] = address_and_price_row.find_element(
                By.CSS_SELECTOR, "td:first-child"
            ).text.strip()
            listing_item["price"] = address_and_price_row.find_element(
                By.CSS_SELECTOR, "td:last-child"
            ).text.strip()

            # Property data
            property_table = table.find_element(By.CSS_SELECTOR, "table.d678m0")
            property_content = property_table.text

            mls_matches = re.search(r"MLS #:\s*(\S+)", property_content)
            beds_matches = re.search(r"Beds:\s*(\d+)", property_content)
            baths_matches = re.search(
                r"Baths:\s*((\d+(\s*\/\s*\d+)?)|\d+)", property_content
            )
            list_agent_matches = re.search(r"List Agent:\s*(.*)", property_content)
            dom_cdom_matches = re.search(
                r"DOM\/CDOM:\s*(\d+\s*\/\s*\d+)", property_content
            )
            tax_position = property_content.find("Tax Annual Amt")
            tax_info = property_content[tax_position + len("Tax Annual Amt") :].strip()
            tax_values = re.search(r"\$\s*([\d,]+)\s*\/\s*(\d+)", tax_info)

            listing_item["MLS"] = mls_matches.group(1) if mls_matches else ""
            listing_item["Beds"] = (beds_matches.group(1) if beds_matches else "",)
            listing_item["Baths"] = (baths_matches.group(1) if baths_matches else "",)
            listing_item["List Agent"] = (
                list_agent_matches.group(1) if list_agent_matches else "",
            )
            listing_item["DOM/CDOM"] = (
                dom_cdom_matches.group(1) if dom_cdom_matches else "",
            )
            listing_item["Tax Annual Amt / Year"] = (
                f"${tax_values.group(1)} / {tax_values.group(2)}" if tax_values else ""
            )

            # Agent Email
            email_link = table.find_element(
                By.CSS_SELECTOR,
                "td.d678m12 span.formula.fieldIE.field.d678m21 a",
            )
            email_link.click()
            driver.switch_to.window(driver.window_handles[-1])
            wait = WebDriverWait(driver, 10)

            try:
                email_link = wait.until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR, 'a[title="Email"]')
                    ),
                    message=f"Email not found for list agent: {listing_item['List Agent']}",
                )
                listing_item["email"] = email_link.text.strip()
                driver.close()

            except TimeoutException as e:
                logger.error(e)

            driver.switch_to.window(original_window)

            logger.info(f"Listing item: {listing_item}")
            data.append(listing_item)

        except Exception as e:
            logger.info("Failed to scrap listing item")
        finally:
            time.sleep(2)

    json_string = json.dumps(data, ensure_ascii=False)
    logger.info(f"Data: {json_string}")
    encoded_bytes = base64.b64encode(json_string.encode("utf-8"))
    encoded_ascii = encoded_bytes.decode("ascii")
    return encoded_ascii


def remove_google_ad(driver: WebDriver):
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
        save_screenshot(driver, "exception_occurred_remove_google_ad")


def login_to_bright_mls(driver: WebDriver, login: str, password: str):
    """Login to Bright MLS website using provided credentials."""

    url = "https://login.brightmls.com/login"
    driver.get(url)

    # Wait until the form is loaded
    logger.info("Waiting for login page to load")
    wait = WebDriverWait(driver, 30)
    wait.until(EC.visibility_of_element_located((By.TAG_NAME, "form")))
    save_screenshot(driver, "login_page_loaded")

    # Fill in form data
    logger.info("Enter login credentials")

    login_field = driver.find_element(By.ID, "username")
    login_field.clear()
    login_field.send_keys(login)

    password_field = driver.find_element(By.ID, "password")
    password_field.clear()
    password_field.send_keys(password)

    time.sleep(5)

    # Submit form data
    submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_button.click()
    logger.info("Login button clicked")
    save_screenshot(driver, "after_login_click")


def open_auto_email_page(driver: WebDriver):
    """Open the Auto Email (New) page."""

    # Wait for dashboard to load
    logger.info("Waiting for dashboard to load")
    wait = WebDriverWait(driver, 180)
    wait.until(
        EC.all_of(
            EC.url_to_be("https://www.brightmls.com/dashboard"),
            EC.visibility_of_element_located((By.ID, "app-children-containerId")),
        )
    )
    save_screenshot(driver, "dashboard_loaded")
    logger.info("Dashboard loaded")
    logger.info("Waiting for 30 sec")
    time.sleep(30)

    # Remove google ad
    remove_google_ad(driver)

    # Click Clients Popup Menu
    logger.info("Clicking Clients Popup Menu")
    wait = WebDriverWait(driver, 60)
    clients_nav_link = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'li[aria-label="Clients"]'))
    )
    clients_nav_link.click()
    save_screenshot(driver, "clients_nav_link_clicked")
    time.sleep(10)

    # Click Auto Email (New) Link
    logger.info("Clicking Auto Email (New) Link")
    auto_email_button = driver.find_element(By.LINK_TEXT, "Auto Email (New)")
    auto_email_button.click()
    save_screenshot(driver, "auto_email_button_clicked")
    time.sleep(15)


def click_accordion_button(
    driver: WebDriver,
    buttons: list[str],
    on_data_scraped: Callable[[str], None],
    on_scrap_failure: Callable[[], None],
):
    """Open listing page for scraping data."""

    accordion_items = driver.find_elements(By.CLASS_NAME, "accordion-item")

    for item in accordion_items:
        accordion_button = item.find_element(By.CLASS_NAME, "accordion-button")
        button_text = accordion_button.text.strip()

        original_window = driver.current_window_handle

        if button_text in buttons:
            logger.info(f"Clicking {button_text} accordion button")
            accordion_button.click()
            save_screenshot(driver, "accordion_button_clicked")
            time.sleep(5)

            logger.info("Clicking Open in Portal button")
            open_in_portal_button = item.find_element(
                By.PARTIAL_LINK_TEXT, "Open in Portal"
            )
            open_in_portal_button.click()
            time.sleep(10)

            driver.switch_to.window(driver.window_handles[-1])
            save_screenshot(driver, "before_scraping")

            try:
                logger.info("Scraping data")
                data = scrap(driver)
                logger.info(f"Scraped data: {data}")
                on_data_scraped(data)

            except Exception as e:
                save_screenshot(driver, "exception_occurred_scraping")
                logger.error(
                    f"Failed to scrap data. Exception occurred: {e}", exc_info=True
                )
                on_scrap_failure()

            save_screenshot(driver, "after_scraping")

            if len(driver.window_handles) > 1:
                driver.close()

            driver.switch_to.window(original_window)


def post_data_to_podio_webhook(podio_url: str, data: str):
    """Post scraped data to podio webhook."""

    try:
        response = requests.post(
            podio_url, json={"data": data}, headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            logger.info(
                f"Post to webhook request successful. Response content: {response.json()}"
            )
        else:
            logger.info(
                f"Post to webhook request failed with status code: {response.status_code}"
            )

    except Exception as e:
        logger.error(
            f"Failed to post data to webhook. Exception occurred: {e}", exc_info=True
        )


def run_script(
    driver: WebDriver,
    login: str,
    password: str,
    desired_buttons: list[str],
    podio_url: str,
):
    login_to_bright_mls(driver, login, password)
    open_auto_email_page(driver)

    click_accordion_button(
        driver,
        desired_buttons,
        on_data_scraped=lambda data: post_data_to_podio_webhook(podio_url, data),
        on_scrap_failure=lambda: post_data_to_podio_webhook(
            podio_url, "Failed to scrap data"
        ),
    )
    logger.info("Program END")


def create_driver():
    options = uc.ChromeOptions()

    options.add_argument("--incognito" if IS_DEV_MODE else "--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")

    driver = uc.Chrome(options=options)
    driver.set_window_size(1920, 1080)

    return driver


@app.before_request
def set_screenshot_dir():
    g.screenshot_dir = create_screenshot_dir()


@app.route("/index", methods=["POST"])
def index():
    if request.method == "POST":
        login = request.form.get("login")
        password = request.form.get("password")
        podio_url = request.form.get("podio_url")
        agents = request.form.get("agents")
        agent_list = agents.split(" | ") if agents else []

        if not login or not password or not podio_url or not agent_list:
            return {"status": 400, "message": "Bad Request"}

        driver = create_driver()

        try:
            run_script(driver, login, password, agent_list, podio_url)
        except Exception as e:
            logger.error(
                f"Running run_script again. Exception occurred: {e}", exc_info=True
            )
            run_script(driver, login, password, agent_list, podio_url)
        finally:
            driver.quit()

        return {"status": 200, "message": "Execution Successful"}
    else:
        return {"status": 400, "message": "Bad Request"}


@app.teardown_request
def cleanup(exception):
    cleanup_old_screenshots()


if __name__ == "__main__":
    if IS_DEV_MODE:
        app.run(host="0.0.0.0", port=5000, debug=True)
    else:
        from waitress import serve

        serve(app, host="0.0.0.0", port=5000)
