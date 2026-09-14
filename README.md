# ssh-vid-mover

A focused Python script for pulling camera recording videos from a remote Linux
machine over SSH and moving them to local storage — safely.

Files are downloaded to a `.part` temporary file first. The remote original is
only deleted after the local size is verified against the remote size. A failed
or interrupted transfer leaves the remote file untouched.

---

## What It Does

- Connects to a remote Linux host over SSH using Paramiko
- Recursively walks a remote recording directory
- Filters files by camera name substrings (configurable at the top of the script)
- Downloads matching files to local storage, preserving the remote directory structure
- Verifies local file size matches remote file size before finalizing
- Deletes the remote original only after a verified successful download
- Cleans up incomplete `.part` files on failure or interrupt
- Prints a transfer summary on completion

---

## Who It's For

Home lab and small camera system operators running Linux on both ends — a
recording node (Raspberry Pi, repurposed desktop, NAS) and a workstation or
storage machine. Useful when you want to pull recordings off a headless system
on a schedule without setting up a full sync tool.

Built for a multi-camera RTSP recording setup. Pairs with
[pyqt-camera-dashboard](https://github.com/BleedingCodes/pyqt-camera-dashboard)
which generates the recordings this script moves.

---

## Requirements

- Python 3.11+
- Linux (developed and tested on Ubuntu / Linux Mint)
- `paramiko` — SSH client library

```bash
pip install -r requirements.txt
```

- SSH access to the remote machine (password authentication)
- The remote recording directory must be accessible to the SSH user

---

## Configuration

Edit the constants at the top of `ssh_vid_mover.py` before running:

```python
DEFAULT_TARGET: str = "192.168.1.105"          # Remote machine IP or hostname
DEFAULT_USERNAME: str = "side"                  # SSH username on the remote machine
DEFAULT_REMOTE_FOLDER: str = "/home/side/Python/Cam_System/recordings"  # Remote directory to search
DEFAULT_DESTINATION: str = "/media/fight/Tb/Downloaded_Recordings"      # Local destination

VIDEO_NAMES: tuple[str, ...] = (
    "d-link",
    "amcrestbullet",
)
```

`VIDEO_NAMES` is a tuple of substrings. Any remote file whose name contains one
of these strings (case-insensitive) will be included in the transfer. For
example, `"d-link"` matches `d-link_2026-07-10_14-53-05.mp4`.

---

## Usage

```bash
python3 ssh_vid_mover.py
```

The script will:

1. Prompt for the SSH password for `DEFAULT_USERNAME@DEFAULT_TARGET`
2. Walk `DEFAULT_REMOTE_FOLDER` recursively
3. Print every file it finds that matches `VIDEO_NAMES`
4. Download each matched file to `DEFAULT_DESTINATION`, preserving subdirectory structure
5. Verify size, finalize the download, delete the remote original
6. Print a summary: files moved successfully, files failed

**Override defaults at runtime without editing the script:**

```bash
python3 ssh_vid_mover.py \
    --target 192.168.1.200 \
    --username pi \
    --remote /home/pi/recordings \
    --dest /mnt/backup/videos \
    --port 22
```

All flags are optional. Any flag not provided falls back to the constant defaults at the top of the script.

---

## Transfer Safety

The download sequence for each file:

```
Download → .part file
         ↓
Verify local size == remote size
         ↓
Rename .part → final filename
         ↓
Delete remote original
```

If any step fails — including a Ctrl-C interrupt — the remote file is not deleted
and the `.part` file is removed. The script continues to the next file rather
than stopping on error.

---

## Example Output

```
2026-07-10 14:53:00  INFO      Connecting to side@192.168.1.105:22 ...
2026-07-10 14:53:01  INFO      Scanning remote directory: /home/side/Python/Cam_System/recordings
2026-07-10 14:53:01  INFO      Found 3 matching file(s).
2026-07-10 14:53:01  INFO      Files queued for transfer:
2026-07-10 14:53:01  INFO        /home/side/Python/Cam_System/recordings/2026-07-10/d-link_14-53-05.mp4
2026-07-10 14:53:01  INFO        /home/side/Python/Cam_System/recordings/2026-07-10/amcrestbullet_14-53-06.mp4
2026-07-10 14:53:01  INFO        /home/side/Python/Cam_System/recordings/2026-07-11/d-link_09-12-44.mp4
2026-07-10 14:53:01  INFO        Remote : /home/side/Python/Cam_System/recordings/2026-07-10/d-link_14-53-05.mp4
2026-07-10 14:53:01  INFO        Local  : /media/fight/Tb/Downloaded_Recordings/2026-07-10/d-link_14-53-05.mp4
2026-07-10 14:53-04  INFO        Status : moved successfully.

...

2026-07-10 14:53:10  INFO      ==============================================
2026-07-10 14:53:10  INFO        Successfully moved : 3
2026-07-10 14:53:10  INFO        Failed             : 0
2026-07-10 14:53:10  INFO      ==============================================
2026-07-10 14:53:10  INFO      Connection closed.
```

---

## Difference From sftp-ultra

[sftp-ultra](https://github.com/BleedingCodes/sftp-ultra) is a full transfer
engine: concurrent workers, resumable downloads, SHA-256 verification, SQLite
journal, overwrite policies, bandwidth throttling, dry-run mode, and a CLI.

`ssh-vid-mover` is a single-file script with no dependencies beyond Paramiko.
Configure it at the top, run it, done. It is the right tool when you want
something simple you can read and modify in ten minutes.

---

## Built by MainbyteLabs

Python tooling for electronics labs, hardware shops, and Linux-based tech teams.

[MainbyteLabs](https://github.com/MR-MainbyteLabs) ·
[LinkedIn](https://linkedin.com/in/michael-rivera-c0ding) ·
mr.mainbytelabs@gmail.com

---

## License

MIT License

Copyright (c) 2026 Michael Rivera

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
