#!/usr/bin/env bash
# Run by .github/workflows/android.yml on an emulator: installs the APK, opens each main
# screen and photographs it. The first launch shows the welcome screens; a relaunch skips
# them (they show once), which is how the rest are reached without tapping through.
#
# No `set -e`: a failing step must not stop the evidence being collected. The log, the
# screenshots and a summary are always written, and the verdict comes last.
set -uo pipefail
apk="$1"
site="https://pashupatastra.vercel.app"
: > summary.txt

adb install -r "$apk" || { echo "install failed" >> summary.txt; exit 1; }
adb logcat -c

alive() { adb shell pidof app.pashupatastra > /dev/null 2>&1; }
shot() {
  sleep "$2"
  adb exec-out screencap -p > "shot-$1.png"
  # The app in front or not, after each screen: where it died, if it did.
  if alive; then echo "$1: running" >> summary.txt; else echo "$1: NOT RUNNING" >> summary.txt; fi
}
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
adb shell input tap 970 2230;  shot 8-more 3      # the More tab, on a 1080x2400 pixel_6

adb logcat -d -b crash > crash.log || true
# The whole log, for diagnosis: a WebView renderer that dies takes the app with it without
# a Java crash, and only the main buffer says so.
adb logcat -d > logcat.txt || true
cat summary.txt
ls -la shot-*.png

# The verdict: running at the end, and every screen reached with the app alive.
alive && ! grep -q "NOT RUNNING" summary.txt
