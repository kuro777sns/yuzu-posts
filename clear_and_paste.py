"""既存データを全削除してからクリップボードの内容を貼り付け"""
import json
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

BASE_DIR = Path(__file__).parent

def load_config():
    with open(BASE_DIR / 'config.json', encoding='utf-8') as f:
        return json.load(f)

def create_driver(config):
    chrome_cfg = config.get('chrome', {})
    data_dir = str(BASE_DIR / chrome_cfg.get('data_dir', 'chrome_data'))
    profile = chrome_cfg.get('profile', 'Default')

    opts = Options()
    opts.add_argument(f'--user-data-dir={data_dir}')
    opts.add_argument(f'--profile-directory={profile}')
    opts.add_argument('--no-first-run')
    opts.add_argument('--no-default-browser-check')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def main():
    config = load_config()
    url = config['spreadsheet_url']

    print('Chrome を起動します...')
    driver = create_driver(config)

    try:
        print('スプレッドシートを開いています...')
        driver.get(url)
        WebDriverWait(driver, 60).until(lambda d: d.title and len(d.title) > 0)
        time.sleep(4)
        print(f'ページタイトル: {driver.title}')

        # 名前ボックスを取得
        name_box = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input')
            )
        )
        time.sleep(1)
        actions = ActionChains(driver)

        # Step 1: A1:H1000 を選択して Delete でクリア
        print('既存データを削除しています...')
        name_box.click()
        time.sleep(0.3)
        actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        time.sleep(0.1)
        name_box.send_keys('A1:H1000')
        time.sleep(0.1)
        actions.send_keys(Keys.ENTER).perform()
        time.sleep(1)
        actions.send_keys(Keys.DELETE).perform()
        time.sleep(2)
        print('削除完了。')

        # Step 2: A1 に移動して Ctrl+V で貼り付け
        print('A1 に貼り付けています...')
        name_box2 = driver.find_element(By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input')
        name_box2.click()
        time.sleep(0.3)
        actions2 = ActionChains(driver)
        actions2.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        time.sleep(0.1)
        name_box2.send_keys('A1')
        time.sleep(0.1)
        actions2.send_keys(Keys.ENTER).perform()
        time.sleep(0.5)
        actions2.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(5)
        print('貼り付け完了！')

    finally:
        driver.quit()

if __name__ == '__main__':
    main()
