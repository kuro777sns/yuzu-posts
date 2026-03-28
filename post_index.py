"""指定インデックスのポストを1件だけ投稿するスクリプト

使い方:
  py post_index.py --file generated/temp_remaining.txt --index 0
"""
import argparse, json, re, time, urllib.request, urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).parent

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
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    blocks = content.split('==========')
    posts = []
    for b in blocks:
        b = b.strip()
        if not b.startswith('[ポスト本文]'):
            continue
        body = b.replace('[ポスト本文]', '').strip()
        parts = re.split(r'■\d+ツイート目', body)
        parts = [p.strip() for p in parts if p.strip()]
        posts.append(parts)
    return posts

def main():
    parser = argparse.ArgumentParser(description='指定インデックスのポストを1件投稿')
    parser.add_argument('--file', required=True, help='投稿ファイル')
    parser.add_argument('--index', type=int, required=True, help='投稿インデックス（0始まり）')
    args = parser.parse_args()

    config = json.load(open(BASE_DIR / 'config.json', encoding='utf-8'))
    token = config['threads_api']['access_token']
    user_id, username = get_user_id(token)
    print(f'アカウント: @{username}')

    posts = extract_posts(args.file)
    if args.index >= len(posts):
        print(f'エラー: インデックス {args.index} は範囲外 (最大 {len(posts)-1})')
        return

    tweets = posts[args.index]
    print(f'投稿 [{args.index}]: {tweets[0][:50]}...')

    if len(tweets) == 1:
        container_id = create_container(user_id, tweets[0], token)
        time.sleep(5)
        post_id = publish_container(user_id, container_id, token)
        print(f'投稿完了: {post_id}')
    else:
        # スレッド投稿
        container_id = create_container(user_id, tweets[0], token)
        time.sleep(5)
        first_id = publish_container(user_id, container_id, token)
        print(f'1ツイート目完了: {first_id}')
        prev_id = first_id
        for tweet in tweets[1:]:
            time.sleep(5)
            cid = create_container(user_id, tweet, token, reply_to_id=prev_id)
            time.sleep(5)
            prev_id = publish_container(user_id, cid, token)
            print(f'返信完了: {prev_id}')

if __name__ == '__main__':
    main()
