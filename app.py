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
    
    # Find chromium and chromedriver dynamically (like Replit)
    chromium_path = shutil.which("chromium")
    chromedriver_path = shutil.which("chromedriver")
    
    if not chromium_path:
        raise RuntimeError("Chromium browser not found. Please install chromium.")
    if not chromedriver_path:
        raise RuntimeError("ChromeDriver not found. Please install chromedriver.")
    
    chrome_options.binary_location = chromium_path
    service = Service(executable_path=chromedriver_path)
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_available_dates_with_slots(driver):
    results = []
    
    bookable_buttons = driver.find_elements(
        By.CSS_SELECTOR, 
        'button.booking-kit_button-bookable_80ba95eb'
    )
    
    for btn in bookable_buttons:
        try:  # Catch stale element errors
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
        except:  # Skip stale elements and continue
            continue
    
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
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Calendly Availability Checker</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
            h1 {
                color: #006bff;
                margin-bottom: 10px;
            }
            p {
                color: #666;
                margin-bottom: 20px;
            }
            input[type="text"] {
                width: 100%;
                padding: 12px;
                font-size: 16px;
                border: 2px solid #ddd;
                border-radius: 6px;
                margin-bottom: 15px;
                box-sizing: border-box;
            }
            input[type="text"]:focus {
                border-color: #006bff;
                outline: none;
            }
            button {
                background: #006bff;
                color: white;
                padding: 12px 30px;
                font-size: 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
            }
            button:hover {
                background: #0056cc;
            }
            button:disabled {
                background: #999;
                cursor: not-allowed;
            }
            .api-info {
                margin-top: 30px;
                padding: 15px;
                background: #f0f7ff;
                border-radius: 6px;
                font-size: 14px;
            }
            code {
                background: #e8e8e8;
                padding: 2px 6px;
                border-radius: 3px;
            }
            #results {
                margin-top: 20px;
                display: none;
            }
            .success {
                background: #e8f5e9;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #4caf50;
            }
            .error {
                background: #ffebee;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #f44336;
            }
            .stats {
                display: flex;
                gap: 20px;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            .stat {
                background: white;
                padding: 15px 20px;
                border-radius: 6px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #006bff;
            }
            .stat-label {
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
            }
            .details-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
                background: white;
                border-radius: 6px;
                overflow: hidden;
            }
            .details-table th, .details-table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }
            .details-table th {
                background: #f5f5f5;
                font-weight: 600;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
            }
            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #006bff;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Calendly Availability Checker</h1>
            <p>Enter a Calendly URL to check available dates and time slots.</p>
            <form id="checkForm">
                <input type="text" id="urlInput" name="url" placeholder="https://calendly.com/username/meeting-type" required>
                <button type="submit" id="submitBtn">Check Availability</button>
            </form>
            <div id="results"></div>
            <div class="api-info">
                <strong>API Usage:</strong><br>
                POST to <code>/check</code> with JSON: <code>{"url": "your_calendly_url"}</code><br>
                Or GET: <code>/check?url=your_calendly_url</code>
            </div>
        </div>
        <script>
            document.getElementById('checkForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const url = document.getElementById('urlInput').value;
                const resultsDiv = document.getElementById('results');
                const submitBtn = document.getElementById('submitBtn');
                
                submitBtn.disabled = true;
                submitBtn.textContent = 'Checking...';
                resultsDiv.style.display = 'block';
                resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div>Checking availability... This may take 15-30 seconds.</div>';
                
                try {
                    const response = await fetch('/check?url=' + encodeURIComponent(url));
                    const data = await response.json();
                    
                    if (data.success) {
                        let detailsHtml = '';
                        if (data.details && data.details.length > 0) {
                            detailsHtml = '<table class="details-table"><tr><th>Date</th><th>Available Slots</th></tr>';
                            data.details.forEach(d => {
                                detailsHtml += '<tr><td>' + d.date + '</td><td>' + d.slots + '</td></tr>';
                            });
                            detailsHtml += '</table>';
                        }
                        
                        resultsDiv.innerHTML = '<div class="success">' +
                            '<div class="stats">' +
                            '<div class="stat"><div class="stat-value">' + data.available_days + '</div><div class="stat-label">Available Days</div></div>' +
                            '<div class="stat"><div class="stat-value">' + data.total_slots + '</div><div class="stat-label">Total Slots</div></div>' +
                            '<div class="stat"><div class="stat-value">' + (data.earliest_date || 'N/A') + '</div><div class="stat-label">Earliest Date</div></div>' +
                            '</div>' +
                            detailsHtml +
                            '</div>';
                    } else {
                        resultsDiv.innerHTML = '<div class="error"><strong>Error:</strong> ' + (data.error || 'Could not check availability') + '</div>';
                    }
                } catch (err) {
                    resultsDiv.innerHTML = '<div class="error"><strong>Error:</strong> ' + err.message + '</div>';
                }
                
                submitBtn.disabled = false;
                submitBtn.textContent = 'Check Availability';
            });
        </script>
    </body>
    </html>
    '''

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

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
