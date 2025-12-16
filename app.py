from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

app = Flask(__name__)

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.binary_location = "/usr/bin/google-chrome"
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def get_current_month(driver):
    """Get the currently displayed month"""
    title = driver.find_element(By.CSS_SELECTOR, '[data-testid="title"]')
    return title.text

def get_available_dates_with_slots(driver):
    """Click each available date and count time slots"""
    results = []
    
    # Find all bookable date buttons
    bookable_buttons = driver.find_elements(
        By.CSS_SELECTOR, 
        'button.booking-kit_button-bookable_80ba95eb'
    )
    
    for btn in bookable_buttons:
        aria_label = btn.get_attribute('aria-label')
        if aria_label and 'Times available' in aria_label:
            date_part = aria_label.split(' - ')[0]
            
            # Click the date to reveal time slots
            btn.click()
            time.sleep(2)  # Wait for slots to load
            
            # Count the time slot buttons
            slot_buttons = driver.find_elements(
                By.CSS_SELECTOR, 
                'button[data-container="time-button"], '
                'button[data-testid="time"], '
                '[data-component="spot-list"] button, '
                '[data-container="spots"] button'
            )
            
            # If above doesn't work, try finding buttons with time patterns
            if not slot_buttons:
                slot_buttons = driver.find_elements(
                    By.XPATH,
                    '//button[contains(@aria-label, "AM") or contains(@aria-label, "PM") or contains(text(), ":")]'
                )
            
            slot_count = len(slot_buttons)
            
            results.append({
                "date": date_part,
                "slots": slot_count
            })
            
            print(f"  {date_part}: {slot_count} slots")
    
    return results

def check_availability(url: str):
    driver = None
    try:
        driver = create_driver()
        
        print("Opening URL...")
        driver.get(url)
        
        # Wait for calendar to load
        print("Waiting for calendar to load...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="calendar"]'))
        )
        time.sleep(3)
        
        # Current month
        current_month = get_current_month(driver)
        print(f"\n=== {current_month} ===")
        current_month_results = get_available_dates_with_slots(driver)
        
        # Next month
        next_month_results = []
        next_month = None
        
        try:
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Go to next month"]'))
            )
            next_button.click()
            time.sleep(3)
            
            next_month = get_current_month(driver)
            print(f"\n=== {next_month} ===")
            next_month_results = get_available_dates_with_slots(driver)
            
        except Exception as e:
            print(f"\nCould not navigate to next month: {e}")
        
        # Summary
        print("\n" + "="*50)
        print("SUMMARY")
        print("="*50)
        
        total_slots = sum(r['slots'] for r in current_month_results) + sum(r['slots'] for r in next_month_results)
        total_days = len(current_month_results) + len(next_month_results)
        
        print(f"Days with availability: {total_days}")
        print(f"Total time slots: {total_slots}")
        
        earliest_date = None
        if current_month_results:
            earliest_date = current_month_results[0]['date']
        elif next_month_results:
            earliest_date = next_month_results[0]['date']
        
        all_results = current_month_results + next_month_results
        
        return {
            "success": True,
            "available_days": total_days,
            "total_slots": total_slots,
            "earliest_date": earliest_date,
            "details": all_results
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "success": False,
            "available_days": 0,
            "total_slots": 0,
            "earliest_date": None,
            "details": [],
            "error": str(e)
        }
    finally:
        if driver:
            try:
                driver.quit()
                print("\nDriver closed")
            except:
                pass

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Calendly Availability Checker</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            input { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }
            button { background: #4CAF50; color: white; padding: 10px 20px; border: none; cursor: pointer; }
            button:hover { background: #45a049; }
            #result { margin-top: 20px; padding: 15px; background: #f4f4f4; border-radius: 5px; }
            .loading { color: #666; }
        </style>
    </head>
    <body>
        <h1>📅 Calendly Availability Checker</h1>
        <p>Enter a Calendly URL to check available dates and time slots</p>
        
        <input type="text" id="url" placeholder="https://calendly.com/..." value="">
        <button onclick="checkAvailability()">Check Availability</button>
        
        <div id="result"></div>
        
        <script>
            async function checkAvailability() {
                const url = document.getElementById('url').value;
                const resultDiv = document.getElementById('result');
                
                if (!url) {
                    resultDiv.innerHTML = '<p style="color: red;">Please enter a URL</p>';
                    return;
                }
                
                resultDiv.innerHTML = '<p class="loading">⏳ Checking availability... This may take 30-60 seconds...</p>';
                
                try {
                    const response = await fetch('/check', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: url})
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        let html = `
                            <h2>✅ Results</h2>
                            <p><strong>Available Days:</strong> ${data.available_days}</p>
                            <p><strong>Total Time Slots:</strong> ${data.total_slots}</p>
                            <p><strong>Earliest Date:</strong> ${data.earliest_date || 'None'}</p>
                        `;
                        
                        if (data.details && data.details.length > 0) {
                            html += '<h3>Details:</h3><ul>';
                            data.details.forEach(d => {
                                html += `<li>${d.date}: ${d.slots} slots</li>`;
                            });
                            html += '</ul>';
                        }
                        
                        resultDiv.innerHTML = html;
                    } else {
                        resultDiv.innerHTML = `<p style="color: red;">❌ Error: ${data.error}</p>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<p style="color: red;">❌ Error: ${error.message}</p>`;
                }
            }
        </script>
    </body>
    </html>
    '''

@app.route('/check', methods=['POST'])
def check():
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"success": False, "error": "No URL provided"}), 400
    
    if "calendly.com" not in url:
        return jsonify({"success": False, "error": "Invalid Calendly URL"}), 400
    
    result = check_availability(url)
    return jsonify(result)

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
