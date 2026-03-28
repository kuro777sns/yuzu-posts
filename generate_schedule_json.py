"""schedule.json を生成するスクリプト（GitHub Actions用）"""
import json, random, re
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent


def parse_posts(text):
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
        posts.append(tweets)
    return posts


def main():
    with open(BASE_DIR / 'config.json', encoding='utf-8') as f:
        config = json.load(f)

    sch = config['schedule']
    start_date = datetime.strptime(sch['start_date'], '%Y-%m-%d')
    start_hour = sch['start_hour']
    start_minute = sch.get('start_minute', 0)
    daily_times = sch['daily_times']
    jitter_min = sch.get('minute_jitter_min', 0)
    jitter_max = sch.get('minute_jitter_max', 0)

    slots = [tuple(map(int, t.split(':'))) for t in daily_times]
    start_hm = start_hour * 60 + start_minute
    current_date = start_date.date()

    slot_idx = next((i for i, (h, m) in enumerate(slots) if h * 60 + m >= start_hm), len(slots))
    if slot_idx >= len(slots):
        current_date += timedelta(days=1)
        slot_idx = 0

    rng = random.Random(42)

    gen_dir = BASE_DIR / 'generated'
    posted_dir = gen_dir / 'posted'
    posted = {p.name for p in posted_dir.glob('*.txt')} if posted_dir.exists() else set()
    paths = sorted(f for f in gen_dir.glob('generated_posts_*.txt') if f.name not in posted)

    schedule = []
    for path in paths:
        text = path.read_text(encoding='utf-8')
        posts = parse_posts(text)
        for idx in range(len(posts)):
            h, m = slots[slot_idx]
            jitter = rng.randint(jitter_min, jitter_max) if jitter_max > 0 else 0
            post_time = datetime.combine(current_date, datetime.min.time()).replace(
                hour=h, minute=m
            ) + timedelta(minutes=jitter)
            schedule.append({
                'file': 'generated/' + path.name,
                'index': idx,
                'datetime': post_time.strftime('%Y-%m-%dT%H:%M:00'),
                'posted': False
            })
            slot_idx += 1
            if slot_idx >= len(slots):
                slot_idx = 0
                current_date += timedelta(days=1)

    out = BASE_DIR / 'schedule.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)
    print(f'schedule.json 生成完了: {len(schedule)} 件')
    for s in schedule:
        print(f"  {s['datetime']}  {s['file']}[{s['index']}]")


if __name__ == '__main__':
    main()
