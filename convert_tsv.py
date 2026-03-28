"""生成ポストファイルをTSV形式に変換するスクリプト"""
import json
import random
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta


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

        # ■Nツイート目 でツリー判定
        thread_parts = re.split(r'■\d+ツイート目\s*', block)
        # thread_parts[0] はヘッダー前のテキスト（通常空）
        tweets = [p.strip() for p in thread_parts if p.strip()]

        if len(tweets) > 1:
            posts.append({"is_thread": True, "tweets": tweets})
        else:
            posts.append({"is_thread": False, "tweets": [block]})
    return posts


def build_tsv(posts, config, links):
    """ポストリストからTSV行を構築"""
    sch = config['schedule']
    start_date = datetime.strptime(sch['start_date'], '%Y-%m-%d')
    start_hour = sch['start_hour']
    start_minute = sch.get('start_minute', 0)
    links_enabled = sch.get('links_enabled', True)
    links_per_day = sch.get('links_per_day', 3) if links_enabled else 0
    delay_min = sch.get('link_delay_min', 30)
    delay_max = sch.get('link_delay_max', 60)

    # daily_times モード
    if 'daily_times' in sch:
        raw_slots = sch['daily_times']
        jitter_min = sch.get('minute_jitter_min', 0)
        jitter_max = sch.get('minute_jitter_max', 0)
        slots = [tuple(map(int, t.split(':'))) for t in raw_slots]

        start_hm = start_hour * 60 + start_minute
        current_date = start_date.date()

        # 初日: start_time 以降の最初のスロットを探す
        slot_idx = next(
            (i for i, (h, m) in enumerate(slots) if h * 60 + m >= start_hm),
            len(slots)
        )
        if slot_idx >= len(slots):
            current_date += timedelta(days=1)
            slot_idx = 0

        links_today = 0
        last_date = current_date
        group_num = 1
        lines = []

        for post in posts:
            if current_date != last_date:
                last_date = current_date
                links_today = 0

            h, m = slots[slot_idx]
            jitter = random.randint(jitter_min, jitter_max) if jitter_max > 0 else 0
            current_time = datetime.combine(current_date, datetime.min.time()).replace(
                hour=h, minute=m
            ) + timedelta(minutes=jitter)

            d = current_time.strftime('%Y/%m/%d')
            hh = f"{current_time.hour}"
            mm = f"{current_time.minute}"

            for tweet in post['tweets']:
                cell_text = tweet.strip().replace('\n', '\r')
                escaped = cell_text.replace('"', '""')
                lines.append(f'{group_num}\t"{escaped}"\t{d}\t{hh}\t{mm}')

            if links_today < links_per_day and links:
                link = random.choice(links)
                link_delay = random.randint(delay_min, delay_max)
                lt = current_time + timedelta(minutes=link_delay)
                link_text = f'{link["text"]}\r{link["url"]}'
                escaped_link = link_text.replace('"', '""')
                lines.append(
                    f'{group_num}\t"{escaped_link}"\t'
                    f'{lt.strftime("%Y/%m/%d")}\t{lt.hour}\t{lt.minute}'
                )
                links_today += 1

            group_num += 1
            slot_idx += 1
            if slot_idx >= len(slots):
                slot_idx = 0
                current_date += timedelta(days=1)

        return '\n'.join(lines)

    # interval モード（後方互換）
    interval = sch['interval']
    interval_min = sch.get('interval_min', interval)
    interval_max = sch.get('interval_max', interval)
    random_min = sch.get('random_minutes', True)
    post_start_hour = sch.get('posting_start_hour', 6)
    post_start_minute = sch.get('posting_start_minute', 0)
    post_end_hour = sch.get('posting_end_hour', 24)
    posts_per_day = sch.get('posts_per_day', 0)

    minute = random.randint(0, 59) if random_min else start_minute
    current_time = start_date.replace(hour=start_hour, minute=minute)
    current_day = current_time.date()
    links_today = 0
    day_count = 0
    group_num = 1
    lines = []

    for post in posts:
        if current_time.date() != current_day:
            current_day = current_time.date()
            links_today = 0
            day_count = 0

        d = current_time.strftime('%Y/%m/%d')
        h = f"{current_time.hour}"
        m = f"{current_time.minute}"

        for tweet in post['tweets']:
            cell_text = tweet.strip().replace('\n', '\r')
            escaped = cell_text.replace('"', '""')
            lines.append(f'{group_num}\t"{escaped}"\t{d}\t{h}\t{m}')

        if links_today < links_per_day and links:
            link = random.choice(links)
            link_delay = random.randint(delay_min, delay_max)
            lt = current_time + timedelta(minutes=link_delay)
            link_text = f'{link["text"]}\r{link["url"]}'
            escaped_link = link_text.replace('"', '""')
            lines.append(
                f'{group_num}\t"{escaped_link}"\t'
                f'{lt.strftime("%Y/%m/%d")}\t{lt.hour}\t{lt.minute}'
            )
            links_today += 1

        day_count += 1
        group_num += 1

        if posts_per_day > 0 and day_count >= posts_per_day:
            next_day = current_time.date() + timedelta(days=1)
            rand_m = random.randint(0, 29) if random_min else 0
            current_time = datetime.combine(next_day, datetime.min.time()).replace(
                hour=post_start_hour, minute=post_start_minute
            ) + timedelta(minutes=rand_m)
            continue

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

    return '\n'.join(lines)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='生成ポスト→TSV変換')
    parser.add_argument('files', nargs='+', help='generated_posts_XXXX.txt')
    parser.add_argument('-d', '--start-date', help='開始日 (YYYY-MM-DD)')
    parser.add_argument('--start-hour', type=int, help='開始時 (0-23)')
    parser.add_argument('-c', '--clipboard', action='store_true', help='クリップボードにコピー')
    parser.add_argument('-o', '--output', help='出力ファイルパス')
    parser.add_argument('--links', action='store_true', default=None, help='リンク挿入を強制ON')
    parser.add_argument('--no-links', action='store_true', help='リンク挿入を強制OFF')
    args = parser.parse_args()

    base = Path(__file__).parent
    with open(base / 'config.json', encoding='utf-8') as f:
        config = json.load(f)
    with open(base / 'links.json', encoding='utf-8') as f:
        links = json.load(f)

    if args.start_date:
        config['schedule']['start_date'] = args.start_date
    if args.start_hour is not None:
        config['schedule']['start_hour'] = args.start_hour
    if args.no_links:
        config['schedule']['links_enabled'] = False
    elif args.links:
        config['schedule']['links_enabled'] = True

    all_posts = []
    for fp in args.files:
        text = Path(fp).read_text(encoding='utf-8')
        all_posts.extend(parse_posts(text))

    tsv = build_tsv(all_posts, config, links)

    if args.clipboard:
        import pyperclip
        pyperclip.copy(tsv)
        print(f'{len(all_posts)}件のポストをクリップボードにコピーしました', file=sys.stderr)

    if args.output:
        Path(args.output).write_text(tsv, encoding='utf-8')
        print(f'{args.output} に出力しました', file=sys.stderr)

    if not args.clipboard and not args.output:
        print(tsv)


if __name__ == '__main__':
    main()
