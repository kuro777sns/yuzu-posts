"""Windowsタスクスケジューラーにゆず投稿タスクを登録するスクリプト"""
import subprocess

SCRIPT_DIR = r'C:\Users\mina-\OneDrive\ドキュメント\Threds_post-generation'
FILE = r'C:\Users\mina-\OneDrive\ドキュメント\Threds_post-generation\generated\temp_remaining.txt'

schedule = [
    (0, '2026/03/24', '19:15'),
    (1, '2026/03/24', '21:15'),
    (2, '2026/03/24', '23:19'),
    (3, '2026/03/26', '10:06'),
    (4, '2026/03/26', '12:05'),
    (5, '2026/03/26', '14:56'),
    (6, '2026/03/26', '17:25'),
    (7, '2026/03/26', '19:20'),
    (8, '2026/03/26', '21:21'),
]

for idx, date, time_str in schedule:
    task_name = f'YuzuPost_{date.replace("/","")}_{time_str.replace(":","")}'
    cmd_str = f'py "{SCRIPT_DIR}\\post_index.py" --file "{FILE}" --index {idx}'

    result = subprocess.run([
        'schtasks', '/create',
        '/tn', task_name,
        '/tr', cmd_str,
        '/sc', 'once',
        '/sd', date,
        '/st', time_str,
        '/f'
    ], capture_output=True, encoding='cp932')

    if result.returncode == 0:
        print(f'OK: {task_name} ({date} {time_str})')
    else:
        print(f'NG: {task_name}')
        print(result.stderr[:200])
