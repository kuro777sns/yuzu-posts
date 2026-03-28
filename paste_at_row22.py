"""A22から直接上書き貼り付けするスクリプト（行削除不要・確実な上書き）"""
import json
import sys
import time
from pathlib import Path
import pyperclip

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

# クリップボードにTSVをコピー
data = open(BASE_DIR / 'output_tsv.txt', encoding='utf-8').read()
pyperclip.copy(data)
lines = [l for l in data.split('\n') if l.strip()]
print(f'クリップボードにコピー完了: {len(lines)}行')

opts = Options()
opts.add_argument(f'--user-data-dir={data_dir}')
opts.add_argument(f'--profile-directory={profile}')
opts.add_argument('--no-first-run')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--disable-blink-features=AutomationControlled')
opts.add_experimental_option('excludeSwitches', ['enable-automation'])

print('Chrome起動...')
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=opts)

try:
    driver.get(config['spreadsheet_url'])
    WebDriverWait(driver, 60).until(lambda d: 'Threads' in d.title)
    time.sleep(5)
    print(f'シート読込完了')

    actions = ActionChains(driver)
    time.sleep(2)
    name_box = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input'))
    )

    # ステップ1: A22:H500を選択してDeleteキーでコンテンツクリア
    print('行22以降をクリア中...')
    name_box.click()
    time.sleep(0.3)
    actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
    time.sleep(0.1)
    name_box.send_keys('A22:H500')
    actions.send_keys(Keys.ENTER).perform()
    time.sleep(1)
    actions.send_keys(Keys.DELETE).perform()
    time.sleep(3)
    print('クリア完了')

    # ステップ2: A22に移動してCtrl+V貼り付け
    print('A22に移動して貼り付け中...')
    name_box2 = driver.find_element(By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input')
    name_box2.click()
    time.sleep(0.3)
    act2 = ActionChains(driver)
    act2.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
    time.sleep(0.1)
    name_box2.send_keys('A22')
    act2.send_keys(Keys.ENTER).perform()
    time.sleep(0.8)

    act3 = ActionChains(driver)
    act3.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
    time.sleep(6)

    # スクリーンショット保存（確認用）
    driver.save_screenshot(str(BASE_DIR / 'verify_final.png'))
    print('スクリーンショット: verify_final.png')
    print('貼り付け完了！')

finally:
    driver.quit()
