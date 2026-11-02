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
# A real live incident, whichever the API lists first: it opens natively (IncidentsScreen.openDetail).
live=$(curl -s https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1/incidents | python3 -c "import sys,json; print(next((i['id'] for i in json.load(sys.stdin) if i['id'].startswith('LIVE-')), ''))" || true)
open "/incidents/${live:-LIVE-unknown}"; shot 4-incident 12
open /ask;                     shot 5-sati-ai 6
open "/ask?q=What%20is%20SQL%20injection%3F"; shot 5b-sati-answer 25
open /observatory;             shot 6-live-attacks 10
open /training;                shot 7-training 15
adb shell input tap 970 2230;  shot 8-more 3      # the More tab, on a 1080x2400 pixel_6

# The app in Hindi and Spanish (per-app language, Android 13+): Home, as a check that the translations
# render. The app restarts for a new language.
for lang in hi-IN es-US; do
  adb shell cmd locale set-app-locales app.pashupatastra --locales "$lang" || true
  adb shell am force-stop app.pashupatastra
  adb shell am start -W -n app.pashupatastra/.MainActivity > /dev/null
  shot "9-home-$lang" 15
done
adb shell cmd locale set-app-locales app.pashupatastra --locales "" || true

adb logcat -d -b crash > crash.log || true
# The whole log, for diagnosis: a WebView renderer that dies takes the app with it without
# a Java crash, and only the main buffer says so.
adb logcat -d > logcat.txt || true
ls -la shot-*.png

# Why the app was stopped, if the system stopped it. Our own force-stop above is expected.
# "depends on provider ... in dying proc" is the emulator's Play services dying and taking
# every app bound to it along (run 41328701921: its font provider), not a fault in this app.
grep -E "Killing [0-9]+:app\.pashupatastra" logcat.txt | grep -v "stop app.pashupatastra due to" >> summary.txt || true
external=$(grep -cE "Killing [0-9]+:app\.pashupatastra.*in dying proc" logcat.txt || true)
# A Java crash in this app (other apps' crashes name their own process). A renderer death is
# not counted: WebTab recovers from it.
ours=$(grep -A3 "FATAL EXCEPTION" logcat.txt | grep -c "Process: app.pashupatastra" || true)
cat summary.txt

# The verdict: running at the end; any screen where it was not running is explained by the
# emulator, and nothing of ours crashed.
alive || exit 1
[ "$ours" = "0" ] || exit 1
if grep -q "NOT RUNNING" summary.txt && [ "$external" = "0" ]; then exit 1; fi
