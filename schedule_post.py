"""スケジュールに従ってThreadsに予約投稿するスクリプト

使い方:
  確認（投稿しない）: python schedule_post.py --dry-run
  実行:               python schedule_post.py
  ファイル指定:       python schedule_post.py generated/generated_posts_0001.txt
  開始日上書き:       python schedule_post.py --start-date 2026-03-27
  開始時上書き:       python schedule_post.py --start-hour 15
"""
import json
import random
import re
import sys
import time
import signal
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta


BASE_DIR = Path(__file__).parent
API_BASE = 'https://graph.threads.net/v1.0'
POSTED_DIR = BASE_DIR / 'generated' / 'posted'


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


def build_schedule(posts: list[dict], config: dict) -> list[dict]:
    """各ポストに投稿予定時刻を付与して返す"""
    sch = config['schedule']
    start_date = datetime.strptime(sch['start_date'], '%Y-%m-%d')
    start_hour = sch['start_hour']
    interval = sch['interval']
    interval_min = sch.get('interval_min', interval)
    interval_max = sch.get('interval_max', interval)
    random_min = sch.get('random_minutes', True)
    post_start_hour = sch.get('posting_start_hour', 6)
    post_start_minute = sch.get('posting_start_minute', 0)
    post_end_hour = sch.get('posting_end_hour', 24)

    fixed_minute = sch.get('start_minute', None)
    minute = fixed_minute if fixed_minute is not None else (random.randint(0, 59) if random_min else 0)
    current_time = start_date.replace(hour=start_hour, minute=minute)

    scheduled = []
    for post in posts:
        scheduled.append({**post, 'scheduled_at': current_time})

        next_interval = random.randint(interval_min, interval_max)
        current_time += timedelta(minutes=next_interval)
        if random_min:
            current_time = current_time.replace(minute=random.randint(0, 59))

        total_min = current_time.hour * 60 + current_time.minute
        end_total = post_end_hour * 60
        start_total = post_start_hour * 60 + post_start_minute
        if total_min >= end_total or total_min < start_total:
            next_day = current_time.date() + timedelta(days=1)
            rand_m = random.randint(0, 29) if random_min else 0
            current_time = datetime.combine(next_day, datetime.min.time()).replace(
                hour=post_start_hour, minute=post_start_minute
            ) + timedelta(minutes=rand_m)

    return scheduled


def api_post(endpoint: str, data: dict, token: str) -> dict:
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


def get_user_id(token: str) -> tuple[str, str]:
    url = f'{API_BASE}/me?fields=id,username&access_token={token}'
    with urllib.request.urlopen(url) as r:
        me = json.loads(r.read().decode('utf-8'))
    return me['id'], me['username']


def create_container(user_id: str, text: str, token: str, reply_to_id: str = None) -> str:
    data = {'media_type': 'TEXT', 'text': text}
    if reply_to_id:
        data['reply_to_id'] = reply_to_id
    result = api_post(f'{user_id}/threads', data, token)
    return result['id']


def publish_container(user_id: str, container_id: str, token: str) -> str:
    result = api_post(f'{user_id}/threads_publish', {'creation_id': container_id}, token)
    return result['id']


def post_single(user_id: str, text: str, token: str, dry_run: bool) -> str:
    if dry_run:
        preview = text[:60] + '...' if len(text) > 60 else text
        print(f'  [DRY-RUN] {preview}')
        return 'dry_run_id'
    container_id = create_container(user_id, text, token)
    time.sleep(2)
    return publish_container(user_id, container_id, token)


def post_thread(user_id: str, tweets: list, token: str, dry_run: bool) -> list:
    ids = []
    parent_id = None
    for i, tweet in enumerate(tweets):
        label = '1本目' if i == 0 else f'返信{i + 1}'
        if dry_run:
            preview = tweet[:60] + '...' if len(tweet) > 60 else tweet
            print(f'  [DRY-RUN] ({label}) {preview}')
            ids.append('dry_run_id')
            continue
        container_id = create_container(user_id, tweet, token, reply_to_id=parent_id)
        time.sleep(2)
        post_id = publish_container(user_id, container_id, token)
        ids.append(post_id)
        parent_id = post_id
        if i < len(tweets) - 1:
            time.sleep(3)
    return ids


def wait_until(target: datetime):
    """target時刻まで待機。1分おきに残り時間を表示"""
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        if remaining > 60:
            # 次の表示まで最大60秒スリープ
            sleep_sec = min(60, remaining - 60) if remaining > 120 else remaining
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            print(f'  待機中... あと {mins}分{secs:02d}秒 ({target.strftime("%m/%d %H:%M")} 投稿予定)', end='\r')
            time.sleep(min(60, remaining))
        else:
            print(f'  待機中... あと {int(remaining)}秒                              ', end='\r')
            time.sleep(1)


def discover_files() -> list[Path]:
    """generated/ 内の未投稿ファイルを連番順に返す"""
    gen_dir = BASE_DIR / 'generated'
    posted_dir = gen_dir / 'posted'
    posted = {p.name for p in posted_dir.glob('*.txt')} if posted_dir.exists() else set()
    files = sorted(gen_dir.glob('generated_posts_*.txt'))
    return [f for f in files if f.name not in posted]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

    # Ctrl+C で安全終了
    signal.signal(signal.SIGINT, lambda s, f: (print('\n\n中断しました。'), sys.exit(0)))

    parser = argparse.ArgumentParser(description='スケジュールに従ってThreadsに投稿')
    parser.add_argument('files', nargs='*', help='generated_posts_XXXX.txt（省略時は自動検出）')
    parser.add_argument('--dry-run', action='store_true', help='投稿せず内容と時刻を確認')
    parser.add_argument('--start-date', help='開始日上書き (YYYY-MM-DD)')
    parser.add_argument('--start-hour', type=int, help='開始時上書き (0-23)')
    parser.add_argument('--start-minute', type=int, help='開始分上書き (0-59)')
    parser.add_argument('--skip-past', action='store_true', help='過去の予定時刻をスキップ（デフォルト: 即投稿）')
    parser.add_argument('--limit', type=int, help='投稿件数の上限')
    args = parser.parse_args()

    config = load_config()
    if args.start_date:
        config['schedule']['start_date'] = args.start_date
    if args.start_hour is not None:
        config['schedule']['start_hour'] = args.start_hour
    if args.start_minute is not None:
        config['schedule']['start_minute'] = args.start_minute

    threads_cfg = config.get('threads_api', {})
    token = threads_cfg.get('access_token')
    if not token:
        print('エラー: config.json に threads_api.access_token がありません')
        sys.exit(1)

    # ファイル収集
    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        paths = discover_files()
        if not paths:
            print('投稿するファイルが見つかりません（generated/ を確認してください）')
            sys.exit(0)

    # ポスト収集
    all_posts = []
    file_map = []  # (post_index, file_path) のマッピング
    for path in paths:
        text = path.read_text(encoding='utf-8')
        posts = parse_posts(text)
        for _ in posts:
            file_map.append(path)
        all_posts.extend(posts)
        print(f'{path.name}: {len(posts)}件読み込み')

    if not all_posts:
        print('投稿が見つかりません')
        sys.exit(0)

    # スケジュール生成
    scheduled_posts = build_schedule(all_posts, config)
    if args.limit:
        scheduled_posts = scheduled_posts[:args.limit]
        file_map = file_map[:args.limit]

    print(f'\n合計 {len(scheduled_posts)} 件{"（DRY-RUN）" if args.dry_run else ""}')
    print('=' * 50)
    for i, post in enumerate(scheduled_posts, 1):
        kind = 'スレッド' if post['is_thread'] else '単体  '
        print(f'  [{i:2d}] {post["scheduled_at"].strftime("%Y/%m/%d %H:%M")}  {kind}  {post["tweets"][0][:30]}...')
    print('=' * 50)

    if args.dry_run:
        print('\nDRY-RUN モード: 実際の投稿はしません。')
        for i, post in enumerate(scheduled_posts, 1):
            print(f'\n[{i}/{len(scheduled_posts)}] {post["scheduled_at"].strftime("%Y/%m/%d %H:%M")} 予定')
            if post['is_thread']:
                post_thread('', post['tweets'], '', dry_run=True)
            else:
                post_single('', post['tweets'][0], '', dry_run=True)
        return

    # アカウント確認
    try:
        user_id, username = get_user_id(token)
        print(f'\nアカウント: @{username} (ID: {user_id})')
    except Exception as e:
        print(f'エラー: アクセストークン確認失敗 - {e}')
        sys.exit(1)

    print('\n投稿を開始します（Ctrl+C で中断）\n')

    POSTED_DIR.mkdir(parents=True, exist_ok=True)
    success = 0
    errors = 0
    last_file = None
    file_post_counts = {}  # ファイルごとの成功投稿数

    for i, post in enumerate(scheduled_posts):
        path = file_map[i]
        scheduled_at = post['scheduled_at']
        now = datetime.now()

        print(f'\n[{i + 1}/{len(scheduled_posts)}] {"スレッド" if post["is_thread"] else "単体"}投稿')
        print(f'  予定: {scheduled_at.strftime("%Y/%m/%d %H:%M")}  ファイル: {path.name}')

        if scheduled_at > now:
            wait_until(scheduled_at)
            print()  # 改行（\r上書きをクリア）
        elif args.skip_past:
            print(f'  → スキップ（過去の予定: {scheduled_at.strftime("%Y/%m/%d %H:%M")}）')
            continue
        else:
            print(f'  → 予定時刻が過去のため即投稿')

        try:
            if post['is_thread']:
                ids = post_thread(user_id, post['tweets'], token, dry_run=False)
                print(f'  → 投稿完了: {len(ids)}ツイート')
            else:
                pid = post_single(user_id, post['tweets'][0], token, dry_run=False)
                print(f'  → 投稿完了: {pid}')
            success += 1
            file_post_counts[path] = file_post_counts.get(path, 0) + 1
        except Exception as e:
            print(f'  → エラー: {e}')
            errors += 1

        # ファイル内の全ポストが完了したら posted/ に移動
        posts_in_file = sum(1 for fp in file_map if fp == path)
        if file_post_counts.get(path, 0) >= posts_in_file:
            dest = POSTED_DIR / path.name
            path.rename(dest)
            print(f'  → {path.name} を posted/ に移動')

    print(f'\n完了: 成功 {success}件 / エラー {errors}件')


if __name__ == '__main__':
    main()
