"""行22の内容を確認するスクリプト"""
import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent
config = json.load(open(BASE_DIR / 'config.json', encoding='utf-8'))
chrome_cfg = config.get('chrome', {})
data_dir = str(BASE_DIR / chrome_cfg.get('data_dir', 'chrome_data'))
profile = chrome_cfg.get('profile', 'Default')

opts = Options()
opts.add_argument(f'--user-data-dir={data_dir}')
opts.add_argument(f'--profile-directory={profile}')
opts.add_argument('--no-first-run')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)

try:
    driver.get(config['spreadsheet_url'])
    WebDriverWait(driver, 60).until(lambda d: 'Threads' in d.title)
    time.sleep(5)

    actions = ActionChains(driver)
    name_box = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input'))
    )
    time.sleep(2)

    # C22に移動
    name_box.click()
    time.sleep(0.3)
    actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
    time.sleep(0.1)
    name_box.send_keys('C22')
    actions.send_keys(Keys.ENTER).perform()
    time.sleep(1.5)

    # スクリーンショット保存
    driver.save_screenshot(str(BASE_DIR / 'verify_row22.png'))

    # 数式バーを確認
    try:
        formula = driver.find_element(By.CSS_SELECTOR, 'input[class*="formula"], textarea[class*="formula"], .cell-input')
        val = formula.get_attribute('value')
        print(f'C22の値: {val}')
    except Exception as e:
        print(f'数式バー読み取り失敗: {e}')

    print('verify_row22.png 保存完了')

finally:
    driver.quit()
