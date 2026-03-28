"""全YuzuPostタスクを削除"""
import subprocess

r = subprocess.run(['schtasks', '/query', '/fo', 'CSV'], capture_output=True, encoding='cp932')
tasks = []
for line in r.stdout.splitlines():
    if 'Yuzu' in line or 'yuzu' in line:
        name = line.split(',')[0].strip('"').lstrip('\\')
        tasks.append(name)
print(f'削除対象: {len(tasks)}件')
deleted = 0
for t in tasks:
    result = subprocess.run(['schtasks', '/delete', '/tn', t, '/f'], capture_output=True, encoding='cp932')
    if result.returncode == 0:
        deleted += 1
print(f'削除完了: {deleted}件')
