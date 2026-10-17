# Android Forensic Toolkit (AFT)

**A Flask-Based Android Digital Forensics Dashboard for Data Acquisition, Artifact Examination, and Evidence Reporting**

## Overview

Android Forensic Toolkit (AFT) is a Python-based digital forensics project that provides a web dashboard for examining selected Android device artifacts, organizing case information, and generating forensic reports.

Built with Flask, HTML, CSS, and JavaScript, the application combines Android Debug Bridge (ADB) integration with CSV and browser-database imports, targeted artifact searches, evidence-file hashing, SQLite database inspection, and HTML report generation.

AFT is designed for digital forensics education, authorized investigations, and laboratory demonstrations. It provides a centralized interface for reviewing available mobile artifacts while acknowledging Android's security restrictions and the limitations of device permissions.

## Problem Statement

Mobile forensic examinations can involve multiple data sources, manual artifact review, device connectivity issues, and time-consuming report preparation. Investigators and students need an organized way to examine available records, identify relevant information, document acquisition attempts, and preserve evidence-handling details.

AFT addresses these needs through a modular dashboard that brings supported acquisition methods, artifact imports, targeted searches, evidence utilities, and report generation into one application.

## Objectives

- Provide a centralized interface for Android forensic examination.
- Detect connected Android devices through ADB.
- Attempt read-only acquisition of supported call logs, SMS records, browser artifacts, and application usage information.
- Import authorized CSV records and supported browser-history databases.
- Search artifacts by a target number or keyword.
- Calculate SHA-256 hashes for evidence files.
- Inspect the schema of uploaded SQLite databases.
- Export case information as JSON.
- Generate a structured HTML forensic report.

## Key Features

### 1. Case Overview Dashboard

- Displays case identifiers and artifact counts.
- Summarizes call records, messages, browser history, and application activity.
- Shows recent communications and artifact activity.
- Provides navigation to individual examination modules.

### 2. Call Log Examination

- Attempts to read accessible call-log records from an authorized Android device using ADB.
- Supports imported call-log CSV files.
- Displays timestamps, contacts or numbers, call direction, duration, and risk labels when available.
- Supports targeted searches and date/time filtering.

### 3. SMS and Message Examination

- Attempts to read accessible SMS records through Android's content provider.
- Supports importing communication records from CSV.
- Displays available timestamps, addresses, message direction, and message content where accessible.
- Supports target-based filtering and date/time filtering.

Access to call logs and messages depends on Android version, device configuration, permissions, and provider restrictions. ADB authorization alone does not guarantee access to private records.

### 4. Browser History Examination

- Attempts supported legacy browser-provider queries.
- Supports acquisition of open browser tabs through the implemented DevTools-based method.
- Supports reading stored browser databases on devices where sufficient privileges are available.
- Supports importing Chrome/Chromium `History` databases and Firefox `places.sqlite` databases.
- Supports CSV import for browser records.
- Displays available timestamps, page titles, URLs, browser names, and visit information.
- Supports date/time filtering and targeted searches.

Stored browser history may require root access or an authorized backup or forensic image. Open-tab acquisition is different from recovering complete browsing history.

### 5. Application History Examination

- Queries Android usage statistics through ADB.
- Attempts to identify installed user applications and available foreground usage sessions.
- Displays supported application names, package identifiers, events, timestamps, and durations.
- Supports re-acquisition and optional periodic refresh through the dashboard.
- Supports CSV imports and date/time filtering.

The available usage information depends on Android's reporting behavior, access restrictions, and the data returned by the device.

### 6. USB Device and ADB Diagnostics

- Detects Android devices using ADB.
- Displays device connection states, including unauthorized, offline, and permission-related conditions.
- Provides ADB diagnostic output to help troubleshoot connectivity.
- Supports restarting the ADB server.
- Displays basic read-only device metadata, such as manufacturer, model, Android version, SDK level, and build fingerprint, for an authorized device.

The application does not bypass Android authentication or security permissions.

### 7. Targeted Extraction and Analysis

- Searches available artifact records by a target phone number or keyword.
- Calculates the number of matching records.
- Identifies first-seen and last-seen timestamps when available.
- Summarizes communication direction and call duration for matching records.
- Provides browser-domain summaries and distinct application counts where applicable.
- Displays matching records for further examination.

Results depend on the records already acquired or imported into the case.

### 8. Evidence Tools

**SHA-256 hashing**
- Calculates a SHA-256 hash for an uploaded evidence file.
- Returns the filename, file size, and calculated hash.

**SQLite schema inspection**
- Opens an uploaded SQLite database for read-only schema inspection.
- Lists database tables and their column names.
- Calculates a SHA-256 hash for the inspected database file.

Hashing supports integrity documentation, but a hash alone does not prove the origin or authenticity of evidence.

### 9. Case Export and Forensic Reporting

- Exports the current case data as JSON.
- Generates an HTML forensic report.
- Includes examination summaries, artifact tables, acquisition outcomes, and available device information.
- Accepts an examiner name and an optional target number or keyword.
- Calculates a SHA-256 hash for the generated HTML report.
- Allows the report to be opened in a browser and printed or saved as PDF.

Report contents depend on the data available in the case and the results of attempted acquisitions.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and artifact processing |
| Flask | Web application and API endpoints |
| HTML, CSS, JavaScript | Dashboard interface and interactive controls |
| Android Debug Bridge (ADB) | Device detection, metadata queries, and supported acquisition attempts |
| SQLite | Inspection of supported browser databases and schemas |
| CSV | Importing communication, browser, and application records |
| JSON | Case storage and data export |
| SHA-256 | Evidence-file and report hashing |
| Bash | Linux setup and launch automation |
| Windows Batch | Windows setup and launch automation |

## Project Structure

```text
AFT_Android_Forensics_Toolkit/
├── app.py
├── requirements.txt
├── README.md
├── run_linux.sh
├── run_windows.bat
├── templates/
│   └── index.html
└── data/
    ├── sample_browser_history.csv
    ├── sample_application_history.csv
    └── sample_communications.csv
```

The application also creates case data and may store imported files, acquired browser databases, and generated reports under `data/` at runtime.

Do not commit private case data, acquired device artifacts, or generated reports containing personal information.

## Requirements

- Python 3
- pip
- A supported operating system: Linux, Kali Linux, or Windows
- Android Platform Tools (ADB) for Android device detection and device-related operations
- A USB data cable and an Android device with USB debugging enabled for applicable live-acquisition functions
- Appropriate device authorization and permissions

The Python dependency declared in `requirements.txt` is Flask.

## Installation and Setup

### Kali Linux / Debian-based Linux

Install the required system packages:

```bash
sudo apt update
sudo apt install python3 python3-venv adb -y
```

Navigate to the extracted project directory:

```bash
cd AFT_Android_Forensics_Toolkit
```

Make the launch script executable and start the application:

```bash
chmod +x run_linux.sh
./run_linux.sh
```

The script creates a virtual environment, installs the Python dependencies, and launches the Flask application.

Alternatively, run the commands manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

### Windows

Install Python 3 and Android Platform Tools if device-related features are required.

Open Command Prompt in the extracted project directory and run:

```bat
run_windows.bat
```

The script creates a virtual environment, installs the dependencies, and starts the application.

## Launching the Dashboard

Once the application starts, open the following address in your browser on the same computer:

**http://127.0.0.1:5000**

Use the navigation panel to access:

- Case Overview
- Call Logs
- Messages / SMS
- Browser History
- Application History
- USB Device
- Evidence Tools
- AFT Report

Keep the terminal open while using the application. Press `Ctrl+C` in that terminal to stop the server.

## Connecting an Android Device

1. Use a data-capable USB cable to connect the Android device.
2. Enable Developer options and USB debugging on the device where permitted.
3. Unlock the device and accept the USB debugging authorization prompt.
4. Verify the connection from the same terminal:

   ```bash
   adb devices -l
   ```

5. Confirm the device state is `device`, rather than `unauthorized` or `offline`.
6. Launch AFT and open the **USB Device** module.
7. Detect the device and review the displayed diagnostics.
8. Open a relevant artifact module and use its acquisition or re-acquisition control.

On Linux, if device permissions are insufficient, install the applicable Android platform-tools udev rules and reconnect the device. Avoid running conflicting ADB servers under different users.

## Importing Data

AFT supports CSV imports for communications, browser history, and application history.

### Communications CSV

Expected columns:

```csv
timestamp,contact,channel,direction,duration,risk
```

Use `CALL` for call records and `SMS`, `MMS`, or `MESSAGE` for message records.

### Browser History CSV

Expected columns:

```csv
timestamp,title,url,browser,visits,risk
```

### Application History CSV

Expected columns:

```csv
timestamp,app_name,package,event,duration,risk
```

Use the import controls in the relevant dashboard module. Include only records you are authorized to examine.

## Using the Evidence Tools

### Calculate a SHA-256 hash

1. Open **Evidence Tools**.
2. Select the evidence file.
3. Run the hash operation.
4. Record the displayed SHA-256 value and file metadata in your case documentation.

### Inspect a SQLite database

1. Open **Evidence Tools**.
2. Select a supported SQLite database.
3. Run the schema inspection operation.
4. Review the table names and column names returned by the application.

Perform forensic examination on authorized working copies and preserve the original evidence according to your laboratory procedures.

## Generating a Forensic Report

1. Open **AFT Report**.
2. Enter the examiner name if applicable.
3. Enter an optional target number or keyword for targeted analysis.
4. Select **Generate**.
5. Review the generated report.
6. Download the HTML report or print it to PDF through your browser.
7. Record the report hash and preserve the report securely.

If no device is connected, the report may use previously imported or stored case data instead of newly acquired records.

## Important Limitations

- Android restricts access to private application data. Not every device exposes call logs or SMS through ADB.
- USB debugging authorization does not grant unrestricted access to private records.
- Stored browser-history acquisition may require root access; imported browser databases or CSV files are alternative supported inputs.
- Open browser tabs are not equivalent to a complete historical browser database.
- Application usage information depends on the data Android exposes to the acquisition methods.
- SHA-256 hashes document file content at the time of hashing; they do not independently establish chain of custody.
- Sample CSV files are provided for demonstration and should not be mistaken for evidence acquired from a real device.
- This project does not guarantee recovery of deleted messages, deleted call logs, or protected application artifacts.

## Security and Responsible Use

AFT is intended for educational use, authorized forensic examinations, and legitimate investigations.

- Examine only devices and data for which you have explicit authorization.
- Protect personal information, credentials, extracted records, and case reports.
- Do not commit real evidence, private device data, tokens, or secrets to a public repository.
- Keep the dashboard bound to its configured local interface unless you have implemented and reviewed appropriate access controls.
- Use secure evidence-handling, documentation, and chain-of-custody procedures.
- Validate the application in a controlled test environment before using it in an operational investigation.

## Future Enhancements

- Additional Android acquisition methods for supported device configurations.
- Expanded artifact parsers and structured analysis.
- Improved case management and examiner identification.
- Stronger audit logging and evidence provenance.
- Enhanced report customization and export options.
- Automated testing and broader compatibility validation.

## Conclusion

Android Forensic Toolkit brings supported Android artifact acquisition attempts, data imports, targeted examination, evidence utilities, and report generation into a single Flask-based dashboard. It provides a foundation for learning and demonstrating mobile digital forensics while recognizing Android security restrictions and the importance of responsible evidence handling.

## Project Information

**Project:** Android Forensic Toolkit (AFT)  
**Category:** Mobile Digital Forensics  
**Primary Language:** Python  
**Interface:** Flask web dashboard  
**Repository Owner:** [muskan786-bit](https://github.com/muskan786-bit/)

*This project is intended for authorized digital forensic examination and educational use.*
