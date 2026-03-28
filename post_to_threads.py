"""Threads API に直接投稿するスクリプト

使い方:
  テスト（投稿しない）: python post_to_threads.py generated/generated_posts_0001.txt --dry-run
  実際に投稿:          python post_to_threads.py generated/generated_posts_0001.txt
  全ファイル投稿:       python post_to_threads.py generated/*.txt

注意:
  - config.json の threads_api.access_token が必要
  - 投稿間隔は30秒以上（API制限対策）
"""
import json
import re
import sys
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path


BASE_DIR = Path(__file__).parent
API_BASE = 'https://graph.threads.net/v1.0'


def load_config():
    with open(BASE_DIR / 'config.json', encoding='utf-8') as f:
        return json.load(f)


def parse_posts(text: str) -> list[dict]:
    """[ポスト本文]...==========形式からポストを抽出"""
    posts = []
    blocks = re.split(r'={5,}|─{5,}', text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.startswith('[ポスト本文]'):
            block = block[len('[ポスト本文]'):].strip()
        if not block:
            continue

        thread_parts = re.split(r'■\d+ツイート目\s*', block)
        tweets = [p.strip() for p in thread_parts if p.strip()]

        if len(tweets) > 1:
            posts.append({'is_thread': True, 'tweets': tweets})
        else:
            posts.append({'is_thread': False, 'tweets': [block]})
    return posts


def api_post(endpoint: str, data: dict, token: str) -> dict:
    """Threads API に POST リクエスト"""
    url = f'{API_BASE}/{endpoint}'
    data['access_token'] = token
    body = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        raise RuntimeError(f'HTTP {e.code}: {err_body}') from e


def create_container(user_id: str, text: str, token: str, reply_to_id: str = None) -> str:
    """メディアコンテナを作成してIDを返す"""
    data = {'media_type': 'TEXT', 'text': text}
    if reply_to_id:
        data['reply_to_id'] = reply_to_id
    result = api_post(f'{user_id}/threads', data, token)
    return result['id']


def publish_container(user_id: str, container_id: str, token: str) -> str:
    """コンテナを公開して投稿IDを返す"""
    result = api_post(f'{user_id}/threads_publish', {'creation_id': container_id}, token)
    return result['id']


def post_single(user_id: str, text: str, token: str, dry_run: bool) -> str:
    """単体投稿"""
    if dry_run:
        print(f'  [DRY-RUN] 投稿: {text[:50]}...' if len(text) > 50 else f'  [DRY-RUN] 投稿: {text}')
        return 'dry_run_id'
    container_id = create_container(user_id, text, token)
    time.sleep(2)
    post_id = publish_container(user_id, container_id, token)
    return post_id


def post_thread(user_id: str, tweets: list, token: str, dry_run: bool) -> list:
    """スレッド投稿（複数ツイートを連結）"""
    post_ids = []
    parent_id = None

    for i, tweet in enumerate(tweets):
        if dry_run:
            label = '(1本目)' if i == 0 else f'(返信{i+1})'
            print(f'  [DRY-RUN] {label}: {tweet[:50]}...' if len(tweet) > 50 else f'  [DRY-RUN] {label}: {tweet}')
            post_ids.append('dry_run_id')
            continue

        container_id = create_container(user_id, tweet, token, reply_to_id=parent_id)
        time.sleep(2)
        post_id = publish_container(user_id, container_id, token)
        post_ids.append(post_id)
        parent_id = post_id

        if i < len(tweets) - 1:
            time.sleep(3)

    return post_ids


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='Threads API に投稿')
    parser.add_argument('files', nargs='+', help='generated_posts_XXXX.txt')
    parser.add_argument('--dry-run', action='store_true', help='投稿せず内容だけ表示')
    parser.add_argument('--interval', type=int, default=30, help='投稿間隔（秒、デフォルト30）')
    args = parser.parse_args()

    config = load_config()
    threads_cfg = config.get('threads_api', {})
    token = threads_cfg.get('access_token')
    if not token:
        print('エラー: config.json に threads_api.access_token がありません', file=sys.stderr)
        sys.exit(1)

    # ユーザーID取得
    url = f'{API_BASE}/me?fields=id,username&access_token={token}'
    with urllib.request.urlopen(url) as r:
        me = json.loads(r.read().decode('utf-8'))
    user_id = me['id']
    print(f'アカウント: @{me["username"]} (ID: {user_id})')

    # 全ファイルのポストを収集
    all_posts = []
    for fp in args.files:
        for path in sorted(Path('.').glob(fp)) if '*' in fp else [Path(fp)]:
            text = path.read_text(encoding='utf-8')
            posts = parse_posts(text)
            all_posts.extend(posts)
            print(f'{path.name}: {len(posts)}件読み込み')

    if not all_posts:
        print('投稿が見つかりません')
        sys.exit(0)

    print(f'\n合計 {len(all_posts)} 件を投稿します{"（DRY-RUN）" if args.dry_run else ""}')
    print('=' * 40)

    success = 0
    errors = 0

    for i, post in enumerate(all_posts, 1):
        print(f'\n[{i}/{len(all_posts)}] {"スレッド" if post["is_thread"] else "単体"}投稿')
        try:
            if post['is_thread']:
                ids = post_thread(user_id, post['tweets'], token, args.dry_run)
                print(f'  → 投稿完了: {len(ids)}ツイート')
            else:
                pid = post_single(user_id, post['tweets'][0], token, args.dry_run)
                print(f'  → 投稿完了: {pid}')
            success += 1
        except Exception as e:
            print(f'  → エラー: {e}', file=sys.stderr)
            errors += 1

        if i < len(all_posts) and not args.dry_run:
            print(f'  {args.interval}秒待機...')
            time.sleep(args.interval)

    print(f'\n完了: 成功 {success}件 / エラー {errors}件')


if __name__ == '__main__':
    main()
