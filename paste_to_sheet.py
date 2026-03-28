"""Seleniumでスプレッドシートにクリップボードの内容を貼り付けるスクリプト

使い方:
  初回ログイン: python paste_to_sheet.py --login
  通常貼り付け: python paste_to_sheet.py

chrome_data/ ディレクトリにセッションが保存されます（.gitignore 推奨）
"""
import json
import sys
import time
import argparse
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


def get_chrome_data_dir(config):
    """config.json の chrome.data_dir からローカルプロファイルパスを返す"""
    chrome_cfg = config.get('chrome', {})
    data_dir = chrome_cfg.get('data_dir', 'chrome_data')
    return BASE_DIR / data_dir


def create_driver(config):
    """ローカル chrome_data でSelenium Chrome起動"""
    chrome_cfg = config.get('chrome', {})
    data_dir = str(get_chrome_data_dir(config))
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


def login_mode(config, wait_seconds=120):
    """初回ログインモード：ブラウザを開いてGoogleログインを待つ"""
    data_dir = get_chrome_data_dir(config)
    print(f'Chrome データディレクトリ: {data_dir}', file=sys.stderr)
    print('Chrome を起動します。Googleにログインしてください...', file=sys.stderr)

    driver = create_driver(config)
    driver.get('https://accounts.google.com/')

    print(f'ブラウザが開きました。Googleにログインしてください（{wait_seconds}秒）', file=sys.stderr)
    print('ログイン後、スプレッドシートを開いて動作確認してください。', file=sys.stderr)

    url = config['spreadsheet_url']
    for i in range(wait_seconds, 0, -10):
        time.sleep(10)
        try:
            title = driver.title
        except Exception:
            print('ブラウザが閉じられました。', file=sys.stderr)
            return
        remaining = i - 10
        if remaining % 30 == 0 or remaining <= 20:
            print(f'  残り {remaining} 秒... (現在: {title})', file=sys.stderr)

    # 終了前にスプレッドシートを開いてセッション確認
    try:
        driver.get(url)
        time.sleep(3)
        title = driver.title
        if 'Sign in' in title or 'ログイン' in title:
            print('警告: まだログインされていません。再度 --login を実行してください。', file=sys.stderr)
        else:
            print(f'ログイン済み確認: {title}', file=sys.stderr)
    except Exception:
        pass

    driver.quit()
    print('ログインセッションを保存しました。', file=sys.stderr)


def paste_mode(config, tsv_content=None):
    """クリップボードの内容をスプレッドシートに貼り付け"""
    url = config['spreadsheet_url']

    print('Chrome を起動します...', file=sys.stderr)
    driver = create_driver(config)

    try:
        print('スプレッドシートを開いています...', file=sys.stderr)
        driver.get(url)

        # シートが読み込まれるまで待機
        WebDriverWait(driver, 60).until(
            lambda d: d.title and len(d.title) > 0
        )
        time.sleep(4)
        title = driver.title
        print(f'ページタイトル: {title}', file=sys.stderr)

        # ログインが必要な場合
        if 'Sign in' in title or 'ログイン' in title or 'Google アカウント' in title:
            print('エラー: ログインが必要です。先に --login を実行してください。', file=sys.stderr)
            driver.quit()
            sys.exit(1)

        # 名前ボックス（セルアドレス入力欄）を探す
        try:
            name_box = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '#A0, input[aria-label="Name Box"], .cell-input')
                )
            )
        except Exception:
            print('名前ボックスが見つかりません。スクリーンショットを保存...', file=sys.stderr)
            driver.save_screenshot(str(BASE_DIR / 'debug_screenshot.png'))
            raise

        time.sleep(1)
        actions = ActionChains(driver)

        # 名前ボックスで A1 に移動（上書きモード）
        name_box.click()
        time.sleep(0.3)
        actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        time.sleep(0.1)
        actions.send_keys('A1').perform()
        time.sleep(0.1)
        actions.send_keys(Keys.ENTER).perform()
        time.sleep(0.5)

        # Chrome起動後にクリップボードを再セット（Chrome起動時のクリア対策）
        if tsv_content:
            import pyperclip
            pyperclip.copy(tsv_content)
            time.sleep(0.5)

        # Ctrl+V で貼り付け
        print('貼り付けています...', file=sys.stderr)
        actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(5)

        print('貼り付け完了。', file=sys.stderr)

    finally:
        driver.quit()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

    config = load_config()

    parser = argparse.ArgumentParser(description='スプレッドシートにTSVを貼り付け')
    parser.add_argument('--login', action='store_true', help='初回ログインモード')
    parser.add_argument('--wait', type=int, default=120, help='ログイン待機秒数（デフォルト120）')
    parser.add_argument('--tsv-file', help='TSVファイルを指定（Chrome起動後に再セット）')
    args = parser.parse_args()

    if args.login:
        login_mode(config, args.wait)
    else:
        tsv_content = None
        if args.tsv_file:
            with open(args.tsv_file, encoding='utf-8') as f:
                tsv_content = f.read()
        paste_mode(config, tsv_content=tsv_content)


if __name__ == '__main__':
    main()
