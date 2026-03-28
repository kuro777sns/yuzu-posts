"""全 generated/ ファイルのポストを Windowsタスクスケジューラに一括登録"""
import json
import random
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent
RANDOM_SEED = 42  # 固定シードで再現可能なスケジュール


def load_config():
    with open(BASE_DIR / 'config.json', encoding='utf-8') as f:
        return json.load(f)


def parse_posts(text: str) -> list[dict]:
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


def build_schedule(posts, config, rng):
    sch = config['schedule']
    start_date = datetime.strptime(sch['start_date'], '%Y-%m-%d')
    start_hour = sch['start_hour']
    start_minute = sch.get('start_minute', 0)

    # daily_times モード
    if 'daily_times' in sch:
        raw_slots = sch['daily_times']
        jitter_min = sch.get('minute_jitter_min', 0)
        jitter_max = sch.get('minute_jitter_max', 0)
        slots = [tuple(map(int, t.split(':'))) for t in raw_slots]

        start_hm = start_hour * 60 + start_minute
        current_date = start_date.date()

        slot_idx = next(
            (i for i, (h, m) in enumerate(slots) if h * 60 + m >= start_hm),
            len(slots)
        )
        if slot_idx >= len(slots):
            current_date += timedelta(days=1)
            slot_idx = 0

        scheduled = []
        for post in posts:
            h, m = slots[slot_idx]
            jitter = rng.randint(jitter_min, jitter_max) if jitter_max > 0 else 0
            current_time = datetime.combine(current_date, datetime.min.time()).replace(
                hour=h, minute=m
            ) + timedelta(minutes=jitter)
            scheduled.append({**post, 'scheduled_at': current_time})
            slot_idx += 1
            if slot_idx >= len(slots):
                slot_idx = 0
                current_date += timedelta(days=1)

        return scheduled

    # interval モード（後方互換）
    interval_min = sch.get('interval_min', sch['interval'])
    interval_max = sch.get('interval_max', sch['interval'])
    random_min = sch.get('random_minutes', True)
    post_start_hour = sch.get('posting_start_hour', 6)
    post_start_minute = sch.get('posting_start_minute', 0)
    post_end_hour = sch.get('posting_end_hour', 24)
    posts_per_day = sch.get('posts_per_day', 0)

    fixed_minute = start_minute
    minute = fixed_minute if not random_min else rng.randint(0, 59)
    current_time = start_date.replace(hour=start_hour, minute=minute)
    current_day = current_time.date()
    day_count = 0

    scheduled = []
    for post in posts:
        scheduled.append({**post, 'scheduled_at': current_time})

        if current_time.date() != current_day:
            current_day = current_time.date()
            day_count = 0
        day_count += 1

        if posts_per_day > 0 and day_count >= posts_per_day:
            next_day = current_time.date() + timedelta(days=1)
            rand_m = rng.randint(0, 29) if random_min else 0
            current_time = datetime.combine(next_day, datetime.min.time()).replace(
                hour=post_start_hour, minute=post_start_minute
            ) + timedelta(minutes=rand_m)
            current_day = current_time.date()
            day_count = 0
            continue

        next_interval = rng.randint(interval_min, interval_max)
        current_time += timedelta(minutes=next_interval)
        if random_min:
            current_time = current_time.replace(minute=rng.randint(0, 59))

        total_min = current_time.hour * 60 + current_time.minute
        end_total = post_end_hour * 60
        start_total = post_start_hour * 60 + post_start_minute
        if total_min >= end_total or total_min < start_total:
            next_day = current_time.date() + timedelta(days=1)
            rand_m = rng.randint(0, 29) if random_min else 0
            current_time = datetime.combine(next_day, datetime.min.time()).replace(
                hour=post_start_hour, minute=post_start_minute
            ) + timedelta(minutes=rand_m)

    return scheduled


def discover_files():
    gen_dir = BASE_DIR / 'generated'
    posted_dir = gen_dir / 'posted'
    posted = {p.name for p in posted_dir.glob('*.txt')} if posted_dir.exists() else set()
    files = sorted(gen_dir.glob('generated_posts_*.txt'))
    return [f for f in files if f.name not in posted]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rng = random.Random(RANDOM_SEED)
    config = load_config()

    paths = discover_files()
    if not paths:
        print('登録するファイルがありません')
        return

    all_posts = []
    file_map = []
    file_index_map = []  # (path, local_index)

    for path in paths:
        text = path.read_text(encoding='utf-8')
        posts = parse_posts(text)
        for local_idx, _ in enumerate(posts):
            file_map.append(path)
            file_index_map.append((path, local_idx))
        all_posts.extend(posts)
        print(f'{path.name}: {len(posts)}件')

    scheduled = build_schedule(all_posts, config, rng)
    now = datetime.now()

    print(f'\n合計 {len(scheduled)} 件のタスクを登録します\n')

    ok = 0
    skip = 0
    ng = 0

    for i, (post, (path, local_idx)) in enumerate(zip(scheduled, file_index_map)):
        scheduled_at = post['scheduled_at']

        # 過去の予定はスキップ
        if scheduled_at <= now:
            skip += 1
            continue

        date_str = scheduled_at.strftime('%Y/%m/%d')
        time_str = scheduled_at.strftime('%H:%M')
        tag = scheduled_at.strftime('%Y%m%d_%H%M')
        task_name = f'YuzuPost_{tag}_{i+1:03d}'

        script_dir = str(BASE_DIR)
        file_path = str(path)
        cmd_str = f'py "{script_dir}\\post_index.py" --file "{file_path}" --index {local_idx}'

        result = subprocess.run([
            'schtasks', '/create',
            '/tn', task_name,
            '/tr', cmd_str,
            '/sc', 'once',
            '/sd', date_str,
            '/st', time_str,
            '/f'
        ], capture_output=True, encoding='cp932')

        if result.returncode == 0:
            print(f'OK [{i+1:3d}] {scheduled_at.strftime("%Y/%m/%d %H:%M")} {path.name}[{local_idx}]')
            ok += 1
        else:
            print(f'NG [{i+1:3d}] {task_name}: {result.stderr[:80]}')
            ng += 1

    print(f'\n登録完了: OK={ok} スキップ={skip} NG={ng}')


if __name__ == '__main__':
    main()
