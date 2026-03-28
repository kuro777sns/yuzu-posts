"""Apps Script の deleteNonPostedRows を実行するスクリプト"""
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
    # スプレッドシートを開く
    driver.get(config['spreadsheet_url'])
    WebDriverWait(driver, 60).until(lambda d: 'Threads' in d.title)
    time.sleep(5)
    print(f'シート読込完了: {driver.title}')

    actions = ActionChains(driver)

    # 拡張機能メニューを探す（テキストで）
    print('拡張機能メニューを探しています...')
    ext_menu = None
    for text in ['拡張機能', 'Extensions']:
        try:
            items = driver.find_elements(By.XPATH, f'//div[@role="menubar"]//div[contains(text(), "{text}")]')
            if items:
                ext_menu = items[0]
                break
        except:
            pass

    if not ext_menu:
        # XPathでメニューバー全体を探す
        try:
            menus = driver.find_elements(By.XPATH, '//div[@role="menubar"]/div')
            print(f'メニューバーアイテム: {[m.text for m in menus]}')
            # "拡張機能" を探す
            for m in menus:
                if '拡張' in m.text or 'Extension' in m.text:
                    ext_menu = m
                    break
        except Exception as e:
            print(f'メニュー検索エラー: {e}')

    if ext_menu:
        print(f'拡張機能メニュー発見: {ext_menu.text}')
        ext_menu.click()
        time.sleep(1.5)

        # マクロサブメニューを探す
        for text in ['マクロ', 'Macros']:
            try:
                items = driver.find_elements(By.XPATH, f'//*[contains(text(), "{text}")]')
                visible = [i for i in items if i.is_displayed()]
                if visible:
                    visible[0].click()
                    time.sleep(1.5)
                    break
            except:
                pass

        # deleteNonPostedRows を探す
        driver.save_screenshot(str(BASE_DIR / 'macro_menu.png'))
        print('macro_menu.png 保存')

        for text in ['deleteNonPostedRows', 'delete', '削除']:
            try:
                items = driver.find_elements(By.XPATH, f'//*[contains(text(), "{text}")]')
                visible = [i for i in items if i.is_displayed()]
                if visible:
                    print(f'実行: {visible[0].text}')
                    visible[0].click()
                    time.sleep(8)  # 削除完了を待つ
                    break
            except Exception as e:
                print(f'エラー: {e}')

        # アラートがあれば確認
        try:
            alert = driver.switch_to.alert
            print(f'アラート: {alert.text}')
            alert.accept()
        except:
            pass

        print('マクロ実行完了')
    else:
        print('拡張機能メニューが見つかりませんでした')

    driver.save_screenshot(str(BASE_DIR / 'after_macro.png'))

finally:
    driver.quit()
