import uuid
from pathlib import Path
from datetime import datetime, timedelta
import time
import shutil

from flask import g


def create_screenshot_dir():
    """
    Creates a unique screenshot directory for the current request using date and a short UUID.
    Stores the path in Flask's g for global access during the request lifecycle.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    unique_id = str(uuid.uuid4())[:8]
    screenshot_dir = Path("logs/screenshots") / date_str / unique_id
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    g.screenshot_dir = screenshot_dir
    return screenshot_dir


def save_screenshot(driver, label):
    """
    Saves a screenshot to the current request's screenshot directory.
    If no directory is set yet, it creates one.
    """
    if not hasattr(g, "screenshot_dir"):
        create_screenshot_dir()

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"{label}_{timestamp}.png"
    file_path = g.screenshot_dir / filename

    try:
        driver.save_screenshot(str(file_path))
        print(f"Screenshot saved: {file_path}")
    except Exception as e:
        print(f"Failed to save screenshot: {e}")


def cleanup_old_screenshots(base_dir="logs/screenshots", days_to_keep=5):
    """
    Deletes screenshot folders older than the specified number of days.

    Args:
        base_dir (str): Base directory where screenshot folders are stored.
        days_to_keep (int): Number of days to retain screenshots.
    """
    cutoff_date = datetime.now() - timedelta(minutes=days_to_keep)
    base_path = Path(base_dir)

    if not base_path.exists():
        return

    for date_dir in base_path.iterdir():
        if date_dir.is_dir():
            try:
                folder_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if folder_date < cutoff_date:
                    shutil.rmtree(date_dir)
                    print(f"Deleted old screenshot folder: {date_dir}")
            except ValueError:
                # Ignore folders that don't follow the date format
                pass
