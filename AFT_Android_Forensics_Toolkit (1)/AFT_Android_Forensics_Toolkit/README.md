# AFT - Android Forensics Toolkit — Separate Module Tabs + USB/ADB Fix

## Run on Kali/Linux
Install prerequisites:
```bash
sudo apt update
sudo apt install adb python3-venv -y
```
Run AFT from the SAME terminal where `adb devices -l` works:
```bash
chmod +x run_linux.sh
./run_linux.sh
```
Open http://127.0.0.1:5000 and select **USB Device** in the left navigation.

## USB troubleshooting
1. Before starting AFT, run `adb devices -l` in that terminal.
2. If ADB shows `unauthorized`, unlock the phone and accept the USB debugging/RSA prompt.
3. If ADB shows `device` but the dashboard doesn't, stop AFT with Ctrl+C and restart it from that same terminal. This version displays the ADB executable path, stdout and stderr to diagnose environment/PATH differences.
4. If the phone doesn't appear at all, check USB data cable, USB debugging, port and Linux USB permissions/udev rules.
5. Avoid running two ADB servers under different users (for example, one with sudo and one as your normal user). If needed, run `adb kill-server && adb start-server`, then `adb devices -l` again.

## Separate tabs
Overview, Call Logs, Messages/SMS, Browser History, Application History, USB Device and Evidence Tools.

## Import formats
- Communications: `timestamp,contact,channel,direction,duration,risk`
- Browser: `timestamp,title,url,browser,visits,risk`
- Apps: `timestamp,app_name,package,event,duration,risk`

USB detection uses ADB and basic read-only device metadata. It does not bypass Android permissions or automatically extract private call/message data.

## Auto-acquisition, targeted extraction, AFT report
- Opening Call Logs / Messages-SMS / Browser History / Application History automatically reads that data from the connected authorized phone over ADB (read-only). Re-acquire any time with the button.
- Each tab has **Targeted extraction**: enter a number/keyword to get match count, first/last seen, direction breakdown, call time and the matching rows.
- **AFT Report** tab: re-acquires everything, optionally adds a Target Analysis, and creates `data/AFT_Report.html` (open at /report/AFT, print to PDF).
- Browser history is usually blocked on modern Android; use CSV import for it. Apps lists installed user apps.

## Date / time filter
Every data tab (Call Logs, Messages/SMS, Browser History, Application History) has a **Date / time filter** (From / To). It narrows the table instantly; clear it with **Clear filter**. Records with no readable timestamp are hidden while a filter is active.

## Browser history (live + stored)
- **Live from phone:** tries the legacy ADB provider first; if blocked (modern Android), it reads Chrome/Brave/Edge/Opera/Samsung Internet/Firefox history databases from a **rooted** phone via `su`. Non-rooted phones cannot expose this over ADB.
- **Stored database:** use **Import browser database** in the Browser History tab with a Chrome `History` or Firefox `places.sqlite` file taken from an authorized backup/image. CSV import still works.

## Browser history (updated)
- **Live (no root):** reads the open tabs of the running Chrome-family browser through its DevTools socket (the same mechanism as `chrome://inspect`). Keep the browser open on the phone with the pages loaded, then open the tab or press *Re-acquire*.
- **Stored (rooted phone):** reads Chrome/Brave/Edge/Opera/Samsung Internet/Firefox history databases (every visit with timestamp, up to 20,000 most recent). Works with `su` or `adb root`.
- **Stored (non-rooted phone):** use *Import browser database* with a `History` / `places.sqlite` file from an authorized backup or image, or a CSV.

## Application history (updated)
Real foreground sessions (start time + duration) are read from Android usage stats (`dumpsys usagestats`). Press *Re-acquire from device* after opening an app, or tick *Auto-refresh from device every 15 s*. Installed apps with no usage events are still listed (without a timestamp).
