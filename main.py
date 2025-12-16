from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import shutil

app = Flask(__name__)

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    chromedriver_path = shutil.which("chromedriver")
    
    if chromium_path:
        chrome_options.binary_location = chromium_path
    
    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)
    
    return driver

def get_available_dates_with_slots(driver):
    results = []
    
    bookable_buttons = driver.find_elements(
        By.CSS_SELECTOR, 
        'button.booking-kit_button-bookable_80ba95eb'
    )
    
    for btn in bookable_buttons:
        aria_label = btn.get_attribute('aria-label')
        if aria_label and 'Times available' in aria_label:
            date_part = aria_label.split(' - ')[0]
            
            btn.click()
            time.sleep(2)
            
            slot_buttons = driver.find_elements(
                By.CSS_SELECTOR, 
                'button[data-container="time-button"], '
                'button[data-testid="time"], '
                '[data-component="spot-list"] button, '
                '[data-container="spots"] button'
            )
            
            if not slot_buttons:
                slot_buttons = driver.find_elements(
                    By.XPATH,
                    '//button[contains(@aria-label, "AM") or contains(@aria-label, "PM") or contains(text(), ":")]'
                )
            
            slot_count = len(slot_buttons)
            results.append({"date": date_part, "slots": slot_count})
    
    return results

def check_availability(url: str):
    driver = create_driver()
    
    try:
        driver.get(url)
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="calendar"]'))
        )
        time.sleep(3)
        
        all_results = []
        
        current_month_results = get_available_dates_with_slots(driver)
        all_results.extend(current_month_results)
        
        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Go to next month"]'))
            )
            next_button.click()
            time.sleep(3)
            
            next_month_results = get_available_dates_with_slots(driver)
            all_results.extend(next_month_results)
        except:
            pass
        
        total_slots = sum(r['slots'] for r in all_results)
        available_days = len(all_results)
        earliest_date = all_results[0]['date'] if all_results else None
        
        return {
            "success": True,
            "available_days": available_days,
            "total_slots": total_slots,
            "earliest_date": earliest_date,
            "details": all_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "available_days": 0,
            "total_slots": 0,
            "earliest_date": None,
            "details": [],
            "error": str(e)
        }
    finally:
        driver.quit()

@app.route('/')
def home():
    return jsonify({
        "service": "Calendly Availability Checker",
        "usage": {
            "GET": "/check?url=your_calendly_url",
            "POST": "/check with JSON {\"url\": \"your_calendly_url\"}"
        }
    })

@app.route('/check', methods=['GET', 'POST'])
def check():
    if request.method == 'POST':
        data = request.json
        url = data.get('url')
    else:
        url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    if "calendly.com" not in url:
        return jsonify({"error": "Invalid Calendly URL"}), 400
    
    result = check_availability(url)
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
