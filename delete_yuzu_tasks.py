"""既存 YuzuPost タスクを全削除"""
import subprocess

result = subprocess.run(['schtasks', '/query', '/fo', 'CSV', '/nh'], capture_output=True)
data = result.stdout.decode('cp932', errors='ignore')

tasks = []
for line in data.splitlines():
    if 'YuzuPost' in line:
        raw = line.split(',')[0]
        name = raw.strip('"').lstrip('\\')
        tasks.append(name)

print(f'{len(tasks)} 件のタスクを削除します')
deleted = 0
for t in tasks:
    r = subprocess.run(['schtasks', '/delete', '/tn', t, '/f'], capture_output=True)
    if r.returncode == 0:
        deleted += 1
    else:
        err = r.stderr.decode('cp932', errors='ignore')
        print(f'FAIL: {t} - {err[:60]}')

print(f'{deleted}/{len(tasks)} 件削除完了')
