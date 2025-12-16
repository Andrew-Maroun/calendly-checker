from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
    driver.set_page_load_timeout(30)
    return driver

def wait_for_calendar(driver, timeout=10):
    """Wait for calendar to be visible"""
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="calendar"]'))
    )

def get_available_date_labels(driver):
    """Extract all available date labels without clicking"""
    date_labels = []
    try:
        bookable_buttons = driver.find_elements(
            By.CSS_SELECTOR, 
            'button.booking-kit_button-bookable_80ba95eb'
        )
        
        for btn in bookable_buttons:
            try:
                aria_label = btn.get_attribute('aria-label')
                if aria_label and 'Times available' in aria_label:
                    date_part = aria_label.split(' - ')[0]
                    date_labels.append(date_part)
            except:
                continue
    except Exception as e:
        print(f"Error getting date labels: {e}")
    
    return date_labels

def count_slots_for_date(driver, date_text, base_url):
    """Navigate to calendar, click date, count slots"""
    try:
        # Go to calendar
        driver.get(base_url)
        wait_for_calendar(driver, timeout=8)
        time.sleep(1)
        
        # Find and click the date button
        bookable_buttons = driver.find_elements(
            By.CSS_SELECTOR, 
            'button.booking-kit_button-bookable_80ba95eb'
        )
        
        target_button = None
        for btn in bookable_buttons:
            try:
                aria_label = btn.get_attribute('aria-label')
                if aria_label and date_text in aria_label and 'Times available' in aria_label:
                    target_button = btn
                    break
            except:
                continue
        
        if not target_button:
            print(f"Button not found for {date_text}")
            return 0
        
        # Click and wait for slots
        target_button.click()
        time.sleep(1.5)
        
        # Count slots
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
        print(f"{date_text}: {slot_count} slots")
        return slot_count
        
    except Exception as e:
        print(f"Error counting slots for {date_text}: {e}")
        return 0

def process_month(driver, base_url):
    """Get all dates and slots for current calendar view"""
    results = []
    
    # Get all available dates
    date_labels = get_available_date_labels(driver)
    print(f"Found {len(date_labels)} available dates")
    
    # Count slots for each date
    for date_text in date_labels:
        slot_count = count_slots_for_date(driver, date_text, base_url)
        if slot_count > 0:
            results.append({
                "date": date_text,
                "slots": slot_count
            })
    
    return results

def check_availability(url: str):
    driver = None
    try:
        driver = create_driver()
        print("Opening URL...")
        driver.get(url)
        wait_for_calendar(driver)
        time.sleep(1)
        
        # ===== CURRENT MONTH =====
        print("\n=== Processing Current Month ===")
        current_month_results = process_month(driver, url)
        
        # ===== NEXT MONTH =====
        print("\n=== Processing Next Month ===")
        next_month_results = []
        
        try:
            # Navigate back to calendar
            driver.get(url)
            wait_for_calendar(driver)
            time.sleep(1)
            
            # Click next month
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Go to next month"]'))
            )
            next_button.click()
            time.sleep(1.5)
            
            # Get current URL (might have changed with month parameter)
            next_month_url = driver.current_url
            
            # Process next month
            next_month_results = process_month(driver, next_month_url)
            
        except TimeoutException:
            print("Next month button not available")
        except Exception as e:
            print(f"Error processing next month: {e}")
        
        # ===== SUMMARY =====
        all_results = current_month_results + next_month_results
        total_slots = sum(r['slots'] for r in all_results)
        total_days = len(all_results)
        earliest_date = all_results[0]['date'] if all_results else None
        
        print(f"\n{'='*50}")
        print(f"SUMMARY: {total_days} days, {total_slots} slots")
        print(f"{'='*50}")
        
        return {
            "success": True,
            "available_days": total_days,
            "total_slots": total_slots,
            "earliest_date": earliest_date,
            "details": all_results
        }
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
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
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #333; margin-top: 0; }
            input { 
                width: 100%; 
                padding: 12px; 
                margin: 15px 0; 
                box-sizing: border-box;
                border: 2px solid #ddd;
                border-radius: 5px;
                font-size: 14px;
            }
            input:focus {
                outline: none;
                border-color: #4CAF50;
            }
            button { 
                background: #4CAF50; 
                color: white; 
                padding: 12px 30px; 
                border: none; 
                cursor: pointer;
                border-radius: 5px;
                font-size: 16px;
                font-weight: 500;
            }
            button:hover { background: #45a049; }
            button:disabled { background: #ccc; cursor: not-allowed; }
            #result { 
                margin-top: 20px; 
                padding: 20px; 
                background: #f9f9f9; 
                border-radius: 5px;
                border-left: 4px solid #4CAF50;
            }
            .loading { color: #666; font-style: italic; }
            .error { color: #d32f2f; }
            .success { color: #4CAF50; }
            ul { line-height: 1.8; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📅 Calendly Availability Checker</h1>
            <p>Enter a Calendly URL to check available dates and time slots</p>
            
            <input type="text" id="url" placeholder="https://calendly.com/username/meeting-type" value="">
            <button id="checkBtn" onclick="checkAvailability()">Check Availability</button>
            
            <div id="result"></div>
        </div>
        
        <script>
            async function checkAvailability() {
                const url = document.getElementById('url').value;
                const resultDiv = document.getElementById('result');
                const btn = document.getElementById('checkBtn');
                
                if (!url) {
                    resultDiv.innerHTML = '<p class="error">Please enter a URL</p>';
                    return;
                }
                
                btn.disabled = true;
                resultDiv.innerHTML = '<p class="loading">⏳ Checking availability... This typically takes 20-40 seconds...</p>';
                
                try {
                    const response = await fetch('/check', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: url})
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        let html = `
                            <h2 class="success">✅ Results</h2>
                            <p><strong>Available Days:</strong> ${data.available_days}</p>
                            <p><strong>Total Time Slots:</strong> ${data.total_slots}</p>
                            <p><strong>Earliest Date:</strong> ${data.earliest_date || 'None'}</p>
                        `;
                        
                        if (data.details && data.details.length > 0) {
                            html += '<h3>Details:</h3><ul>';
                            data.details.forEach(d => {
                                html += `<li><strong>${d.date}:</strong> ${d.slots} slot${d.slots !== 1 ? 's' : ''}</li>`;
                            });
                            html += '</ul>';
                        }
                        
                        resultDiv.innerHTML = html;
                    } else {
                        resultDiv.innerHTML = `<p class="error">❌ Error: ${data.error}</p>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<p class="error">❌ Network Error: ${error.message}</p>`;
                } finally {
                    btn.disabled = false;
                }
            }
            
            // Allow Enter key to submit
            document.getElementById('url').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    checkAvailability();
                }
            });
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
