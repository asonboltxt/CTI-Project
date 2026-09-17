from pathlib import Path
path = Path('app.py')
text = path.read_text(encoding='utf-8')
backup = Path('app_before_phase2.py')
if not backup.exists(): backup.write_text(text, encoding='utf-8')
if 'from phase2 import register_phase2' not in text:
    text = 'from phase2 import register_phase2\n' + text
if 'register_phase2(app)' not in text:
    marker = 'app = Flask(__name__)'
    if marker not in text:
        raise SystemExit('Could not find app = Flask(__name__). Register Phase 2 manually.')
    text = text.replace(marker, marker + '\nregister_phase2(app)', 1)
path.write_text(text, encoding='utf-8')
print('Patched app.py. Backup: app_before_phase2.py')
