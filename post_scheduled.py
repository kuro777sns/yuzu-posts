"""GitHub Actions から呼ばれる自動投稿スクリプト
JST で schedule.json を読み、±15分以内の未投稿ポストをThreadsに投稿する
"""
import json, os, re, time, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE_DIR = Path(__file__).parent
JST = timezone(timedelta(hours=9))
API_BASE = 'https://graph.threads.net/v1.0'


def api_post(endpoint, data, token):
    url = f'{API_BASE}/{endpoint}'
    data['access_token'] = token
    body = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode('utf-8'))


def get_user_id(token):
    url = f'{API_BASE}/me?fields=id,username&access_token={token}'
    with urllib.request.urlopen(url) as r:
        me = json.loads(r.read().decode('utf-8'))
    return me['id'], me['username']


def create_container(user_id, text, token, reply_to_id=None):
    data = {'media_type': 'TEXT', 'text': text}
    if reply_to_id:
        data['reply_to_id'] = reply_to_id
    return api_post(f'{user_id}/threads', data, token)['id']


def publish_container(user_id, container_id, token):
    return api_post(f'{user_id}/threads_publish', {'creation_id': container_id}, token)['id']


def extract_posts(filepath):
    text = Path(filepath).read_text(encoding='utf-8')
    blocks = re.split(r'={5,}|─{5,}', text)
    posts = []
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
        posts.append(tweets)
    return posts


def post_tweets(user_id, tweets, token):
    if len(tweets) == 1:
        cid = create_container(user_id, tweets[0], token)
        time.sleep(5)
        post_id = publish_container(user_id, cid, token)
        print(f'  投稿完了: {post_id}')
        return post_id
    else:
        cid = create_container(user_id, tweets[0], token)
        time.sleep(5)
        first_id = publish_container(user_id, cid, token)
        print(f'  1ツイート目: {first_id}')
        prev_id = first_id
        for tweet in tweets[1:]:
            time.sleep(5)
            cid = create_container(user_id, tweet, token, reply_to_id=prev_id)
            time.sleep(5)
            prev_id = publish_container(user_id, cid, token)
            print(f'  返信: {prev_id}')
        return first_id


def main():
    token = os.environ.get('THREADS_ACCESS_TOKEN')
    if not token:
        # ローカル実行時は config.json から読む
        with open(BASE_DIR / 'config.json', encoding='utf-8') as f:
            config = json.load(f)
        token = config['threads_api']['access_token']

    schedule_path = BASE_DIR / 'schedule.json'
    with open(schedule_path, encoding='utf-8') as f:
        schedule = json.load(f)

    now_jst = datetime.now(JST).replace(tzinfo=None)
    window = timedelta(minutes=15)

    due = [
        (i, s) for i, s in enumerate(schedule)
        if not s['posted']
        and abs(datetime.fromisoformat(s['datetime']) - now_jst) <= window
    ]

    if not due:
        print(f'[{now_jst.strftime("%Y-%m-%d %H:%M")} JST] 投稿予定なし')
        return

    user_id, username = get_user_id(token)
    print(f'アカウント: @{username}')

    changed = False
    for i, s in due:
        print(f'\n投稿: {s["datetime"]}  {s["file"]}[{s["index"]}]')
        try:
            posts = extract_posts(BASE_DIR / s['file'])
            if s['index'] >= len(posts):
                print(f'  エラー: インデックス {s["index"]} が範囲外')
                continue
            tweets = posts[s['index']]
            print(f'  内容: {tweets[0][:40]}...')
            post_tweets(user_id, tweets, token)
            schedule[i]['posted'] = True
            changed = True
        except Exception as e:
            print(f'  エラー: {e}')

    if changed:
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        print('\nschedule.json 更新完了')


if __name__ == '__main__':
    main()
