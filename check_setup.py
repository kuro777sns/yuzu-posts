import sys
print(f"Python: {sys.version}")

modules = ["selenium", "webdriver_manager", "pyperclip"]
for m in modules:
    try:
        __import__(m)
        print(f"  OK: {m}")
    except ImportError:
        print(f"  MISSING: {m}")
