# Blockchain Document Protection System - Startup Scripts

## Quick Start

### 🚀 Start Everything (Recommended)
```
start_everything.bat
```
This script will:
1. Check all prerequisites (Python, Node.js, Truffle, IPFS)
2. Install missing Python dependencies
3. Start IPFS Desktop (if installed)
4. Start the blockchain network (Truffle Develop)
5. Start the Flask web application
6. Verify all services are running
7. Open your browser automatically

**First time users:** Run this script!

---

## Other Useful Scripts

### ✅ Check Status
```
check_status.bat
```
Checks if all services are running and shows their status:
- IPFS Daemon (port 5001)
- Blockchain RPC (port 9545)
- Flask Application (port 5000)

Use this to verify everything is working correctly.

### 🛑 Stop Everything
```
stop_everything.bat
```
Cleanly stops all services:
- Flask Application (Python)
- Blockchain Network (Node.js/Truffle)
- IPFS Desktop (optional - asks before stopping)

### 🔧 Quick Start (Legacy)
```
quick_start.bat
```
Faster startup without extensive checks. Starts services in separate windows.

### ⚙️ Individual Scripts

**Start Blockchain Only:**
```
start_blockchain.bat
```

**Start Flask App Only:**
```
run_app.bat
```

**Install Dependencies:**
```
install.bat
```

---

## Service Information

### 🌐 Web Application
- **URL:** http://127.0.0.1:5000
- **Framework:** Flask
- **Demo Credentials:**
  - Admin: `admin` / `admin123`
  - Investigator: `investigator` / `investigator123`
  - Demo User: `demo` / `demo123`
  - Viewer: `viewer` / `viewer123`

### ⛓️ Blockchain Network
- **RPC URL:** http://127.0.0.1:9545
- **Type:** Truffle Develop
- **Network ID:** 1337
- **Contract:** 0x1DD4fb45C1cdC8C3f32cbaA60464c8107D4D4058
- **Accounts:** 10 pre-funded test accounts (100 ETH each)

### 📦 IPFS
- **API URL:** http://127.0.0.1:5001
- **Type:** IPFS Desktop (Kubo)
- **Purpose:** Decentralized evidence storage
- **Install:** `winget install --id IPFS.IPFS-Desktop -e`

---

## Prerequisites

### Required Software
1. **Python 3.8+** - https://python.org
2. **Node.js 18+** - https://nodejs.org
3. **Truffle** - `npm install -g truffle`

### Optional But Recommended
4. **IPFS Desktop** - `winget install --id IPFS.IPFS-Desktop -e`

---

## Troubleshooting

### Port Already in Use
If you get "port already in use" errors:
1. Run `stop_everything.bat`
2. Wait 5 seconds
3. Run `start_everything.bat` again

### IPFS Not Connecting
1. Check if IPFS Desktop is running (system tray icon)
2. Open IPFS Desktop and check status
3. Try restarting IPFS Desktop

### Blockchain Not Starting
1. Close the blockchain window
2. Navigate to `hello-eth` folder
3. Run `truffle develop` manually to see errors
4. Check if Node.js version is compatible (18+ recommended)

### Flask Won't Start
1. Check if port 5000 is available
2. Run `python --version` to verify Python installation
3. Run `pip install -r requirements.txt` in Document_Protection_Blockchain folder
4. Check the Flask window for error messages

### Unicode/Emoji Errors
The scripts now automatically set UTF-8 encoding. If you still see encoding errors:
- Run the command prompt as Administrator
- Or set these environment variables manually:
  ```
  set PYTHONUTF8=1
  set PYTHONIOENCODING=utf-8
  ```

---

## Environment Variables

The startup scripts set these automatically:

- `PYTHONUTF8=1` - Enable UTF-8 output in Python
- `PYTHONIOENCODING=utf-8` - UTF-8 encoding for file I/O
- `REQUIRE_IPFS=1` - Require IPFS connection (no local fallback)

To change IPFS requirement, edit the batch files or set manually:
```
set REQUIRE_IPFS=0
```

---

## Manual Startup (Advanced)

If you prefer to start services manually:

1. **Start IPFS:**
   - Open IPFS Desktop from Start Menu
   - Wait for green "Ready" status

2. **Start Blockchain:**
   ```
   cd hello-eth
   truffle develop
   ```
   Keep this terminal open

3. **Start Flask App:**
   ```
   cd Document_Protection_Blockchain
   set PYTHONUTF8=1
   set PYTHONIOENCODING=utf-8
   set REQUIRE_IPFS=1
   python MainEnhanced.py
   ```
   Keep this terminal open

4. **Access Application:**
   Open browser to http://127.0.0.1:5000

---

## Files Overview

```
Blockchain_doc_protection/
├── start_everything.bat       ← Main startup script (USE THIS!)
├── check_status.bat            ← Check if services are running
├── stop_everything.bat         ← Stop all services
├── quick_start.bat             ← Fast startup (legacy)
├── install.bat                 ← Install dependencies only
├── start_blockchain.bat        ← Start blockchain only
├── run_app.bat                 ← Start Flask app only
├── STARTUP_SCRIPTS_README.md   ← This file
│
├── Document_Protection_Blockchain/
│   ├── MainEnhanced.py         ← Main Flask application
│   ├── requirements.txt        ← Python dependencies
│   └── ...
│
└── hello-eth/
    ├── bin/
    │   └── runBlockchain.bat   ← Blockchain startup helper
    └── ...
```

---

## Support

For issues or questions:
1. Check this README
2. Run `check_status.bat` to diagnose problems
3. Check the individual service windows for error messages
4. Review the logs in Document_Protection_Blockchain folder

---

**Version:** 1.0  
**Last Updated:** January 7, 2026  
**Compatible With:** Windows 10/11
