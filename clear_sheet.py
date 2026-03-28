"""スプレッドシートの内容を全削除するスクリプト"""
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


def clear_sheet():
    config = load_config()
    url = config['spreadsheet_url']

    print('Chrome を起動します...', file=sys.stderr)
    driver = create_driver(config)

    try:
        print('スプレッドシートを開いています...', file=sys.stderr)
        driver.get(url)

        WebDriverWait(driver, 60).until(
            lambda d: d.title and len(d.title) > 0
        )
        time.sleep(4)
        title = driver.title
        print(f'ページタイトル: {title}', file=sys.stderr)

        if 'Sign in' in title or 'ログイン' in title or 'Google アカウント' in title:
            print('エラー: ログインが必要です。先に paste_to_sheet.py --login を実行してください。', file=sys.stderr)
            driver.quit()
            sys.exit(1)

        # 名前ボックスで A1 に移動
        name_box = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input')
            )
        )
        time.sleep(1)
        actions = ActionChains(driver)

        name_box.click()
        time.sleep(0.3)
        actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        time.sleep(0.1)
        actions.send_keys('A1').perform()
        time.sleep(0.1)
        actions.send_keys(Keys.ENTER).perform()
        time.sleep(0.5)

        # Ctrl+Shift+End で最終セルまで選択
        print('全セルを選択しています...', file=sys.stderr)
        actions.key_down(Keys.CONTROL).key_down(Keys.SHIFT).send_keys(Keys.END).key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()
        time.sleep(1)

        # Delete キーで内容を削除
        print('内容を削除しています...', file=sys.stderr)
        actions.send_keys(Keys.DELETE).perform()
        time.sleep(3)

        print('削除完了。', file=sys.stderr)

    finally:
        driver.quit()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    clear_sheet()
