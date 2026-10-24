#!/usr/bin/env bash
set -euo pipefail
command -v flutter >/dev/null 2>&1 || { echo "Flutter SDK not found. Install Flutter and Android Studio first." >&2; exit 1; }
flutter doctor
flutter create --platforms=android --org com.nextrade --project-name nextrade .
python3 - <<'PYGRADLE'
from pathlib import Path
import re
candidates = [Path('android/app/build.gradle.kts'), Path('android/app/build.gradle')]
for gradle in candidates:
    if not gradle.exists():
        continue
    source = gradle.read_text()
    updated = source
    if gradle.suffix == '.kts':
        updated = re.sub(r'(?m)^\s*minSdk\s*=\s*(?:flutter\.minSdkVersion|[0-9]+)', '        minSdk = 24', updated, count=1)
    else:
        updated = re.sub(r'(?m)^\s*minSdkVersion\s+(?:flutter\.minSdkVersion|[0-9]+)', '        minSdkVersion 24', updated, count=1)
    if updated == source and not re.search(r'(?m)^\s*minSdk\s*=\s*24|^\s*minSdkVersion\s+24', source):
        raise SystemExit(f'Could not safely set Android minSdk 24 in {gradle}')
    gradle.write_text(updated)
    print(f'Configured Android minSdk 24 in {gradle}')
    break
else:
    raise SystemExit('Flutter scaffold did not create android/app/build.gradle(.kts)')
PYGRADLE
python3 - <<'PYMANIFEST'
from pathlib import Path
import re
manifest = Path("android/app/src/main/AndroidManifest.xml")
source = manifest.read_text()
if "android.permission.INTERNET" not in source:
    source = re.sub(r"(?m)^\s*<application", '    <uses-permission android:name="android.permission.INTERNET" />\n    <application', source, count=1)
    manifest.write_text(source)
PYMANIFEST
mkdir -p android/app/src/debug
cat > android/app/src/debug/AndroidManifest.xml <<'EOF'
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application android:usesCleartextTraffic="true" />
</manifest>
EOF
flutter pub get
flutter analyze
flutter test
printf '\nAndroid scaffold is ready. Build a release APK with:\nflutter build apk --release\n'
