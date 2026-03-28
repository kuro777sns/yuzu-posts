"""スプレッドシートの22行目以降（未投稿行）を削除するスクリプト"""
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

config = load_config()
url = config['spreadsheet_url']

print('Chrome起動...')
driver = create_driver(config)

try:
    driver.get(url)
    WebDriverWait(driver, 60).until(lambda d: 'スプレッドシート' in d.title or 'Spreadsheet' in d.title or 'Threads' in d.title)
    time.sleep(5)
    print(f'タイトル: {driver.title}')

    actions = ActionChains(driver)

    # 名前ボックスで行22を選択
    name_box = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input')
        )
    )
    name_box.click()
    time.sleep(0.3)
    actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
    time.sleep(0.1)
    name_box.send_keys('22:1000')
    time.sleep(0.1)
    actions.send_keys(Keys.ENTER).perform()
    time.sleep(1.5)
    print('行22〜1000を選択')

    # 右クリックでコンテキストメニュー表示
    # シートのセルエリアで右クリック（行が選択された状態）
    body = driver.find_element(By.TAG_NAME, 'body')
    # JavaScriptでcanvasの中央を右クリック
    driver.execute_script("""
        var evt = new MouseEvent('contextmenu', {
            bubbles: true,
            cancelable: true,
            clientX: 400,
            clientY: 300
        });
        document.elementFromPoint(400, 300).dispatchEvent(evt);
    """)
    time.sleep(1.5)

    # "行を削除" メニュー項目を探してクリック
    delete_menu = None
    for text in ['行を削除', 'Delete rows', '行の削除', 'Delete row']:
        items = driver.find_elements(By.XPATH, f'//*[contains(text(), "{text}")]')
        if items:
            delete_menu = items[0]
            break

    if delete_menu:
        delete_menu.click()
        time.sleep(3)
        print('行削除完了！')
    else:
        # Escで閉じてEdit メニューから試みる
        actions.send_keys(Keys.ESCAPE).perform()
        time.sleep(0.5)
        print('コンテキストメニューで見つからず。Editメニューを試みます...')

        # 再度行選択
        name_box2 = driver.find_element(By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input')
        name_box2.click()
        time.sleep(0.3)
        act2 = ActionChains(driver)
        act2.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        name_box2.send_keys('22:1000')
        act2.send_keys(Keys.ENTER).perform()
        time.sleep(1)

        # 編集メニューをクリック
        edit_menu = None
        for label in ['編集', 'Edit']:
            items = driver.find_elements(By.XPATH, f'//div[@role="menubar"]//div[text()="{label}"]')
            if items:
                edit_menu = items[0]
                break
        if not edit_menu:
            edit_menu = driver.find_element(By.XPATH, '//div[@aria-label="編集" or @aria-label="Edit"]')

        edit_menu.click()
        time.sleep(1)

        for text in ['行を削除', 'Delete rows', '行の削除']:
            items = driver.find_elements(By.XPATH, f'//*[contains(text(), "{text}")]')
            if items:
                items[0].click()
                time.sleep(2)
                print('行削除完了（Editメニュー経由）！')
                break

    time.sleep(2)
    print('処理完了')

finally:
    driver.quit()
