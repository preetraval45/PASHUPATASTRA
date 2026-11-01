#!/usr/bin/env bash
# Run by .github/workflows/android.yml on an emulator: installs the APK, opens each main
# screen and photographs it. The first launch shows the welcome screens; a relaunch skips
# them (they show once), which is how the rest are reached without tapping through.
set -euo pipefail
apk="$1"
site="https://pashupatastra.vercel.app"

adb install -r "$apk"
adb logcat -c

shot() { sleep "$2"; adb exec-out screencap -p > "shot-$1.png"; }
open() { adb shell am start -W -a android.intent.action.VIEW -d "$site$1" app.pashupatastra/.MainActivity > /dev/null; }

adb shell am start -W -n app.pashupatastra/.MainActivity > /dev/null
shot 1-welcome 8
adb shell am force-stop app.pashupatastra
adb shell am start -W -n app.pashupatastra/.MainActivity > /dev/null
shot 2-home 15
open /incidents;               shot 3-incidents 8
open /incidents/INC-2026-0904; shot 4-incident 15
open /ask;                     shot 5-sati-ai 15
open /observatory;             shot 6-live-attacks 10
open /training;                shot 7-training 15

# Still running, and nothing in the crash buffer.
adb shell pidof app.pashupatastra
adb logcat -d -b crash > crash.log || true
ls -la shot-*.png
