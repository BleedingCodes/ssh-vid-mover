
"""
ssh_vid_mover.py — SSH camera recording mover.
 
Connects to a remote Linux host over SSH/SFTP, finds video files
whose names contain any of the strings in VIDEO_NAMES, downloads
them using a safe .part pattern with size verification, and deletes
the originals only after a successful transfer.
 
USAGE
-----
Run with defaults (edit constants below or use CLI flags):
    python ssh_vid_mover.py
 
Override at runtime:
    python ssh_vid_mover.py --target 192.168.1.200 --username pi \
        --remote /home/pi/recordings --dest /mnt/backup/videos
 
REQUIREMENTS
------------
    pip install paramiko
 
SECURITY NOTE
-------------
This tool uses RejectPolicy for SSH host-key checking. The remote
host must already be in your ~/.ssh/known_hosts before first use.
To add it:
    ssh-keyscan -H <target-ip> >> ~/.ssh/known_hosts
or connect manually once with the standard ssh client.
"""
 
import argparse
import getpass
import logging
import os
import stat
import sys
from pathlib import Path, PurePosixPath
 
import paramiko
 
# ---------------------------------------------------------------------------
# Defaults — override via CLI flags or edit here.
# ---------------------------------------------------------------------------
 
DEFAULT_TARGET: str = "192.168.1.105"
DEFAULT_USERNAME: str = "side"
DEFAULT_REMOTE_FOLDER: str = "/home/side/Python/Cam_System/recordings"
DEFAULT_DESTINATION: str = "/media/fight/Tb/Downloaded_Recordings"
 
VIDEO_NAMES: tuple[str, ...] = (
    "d-link",
    "amcrestbullet",
)
 
# Only files with these extensions are eligible for transfer.
# Guards against name-matching non-video files that would be deleted.
VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".ts",
    ".m4v",
)
 
# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
 
 
# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
 
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move camera recordings from a remote host over SSH/SFTP.",
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        help=f"Remote host IP or hostname (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help=f"SSH username (default: {DEFAULT_USERNAME})",
    )
    parser.add_argument(
        "--remote",
        default=DEFAULT_REMOTE_FOLDER,
        help=f"Remote directory to search (default: {DEFAULT_REMOTE_FOLDER})",
    )
    parser.add_argument(
        "--dest",
        default=DEFAULT_DESTINATION,
        help=f"Local destination directory (default: {DEFAULT_DESTINATION})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=22,
        help="SSH port (default: 22)",
    )
    return parser.parse_args()
 
 
# ---------------------------------------------------------------------------
# remote_walk
# ---------------------------------------------------------------------------
 
def remote_walk(sftp: paramiko.SFTPClient, remote_directory: str):
    """
    Recursively walk a remote directory over SFTP.
    Yields full remote file paths (strings) for regular files only.
    """
    try:
        entries = sftp.listdir_attr(remote_directory)
    except IOError as exc:
        log.warning("Cannot list directory %s: %s", remote_directory, exc)
        return
 
    for item in entries:
        remote_path = str(
            PurePosixPath(remote_directory) / item.filename
        )
        if stat.S_ISDIR(item.st_mode):
            yield from remote_walk(sftp, remote_path)
        elif stat.S_ISREG(item.st_mode):
            yield remote_path
 
 
# ---------------------------------------------------------------------------
# create_transfer_list
# ---------------------------------------------------------------------------
 
def create_transfer_list(
    sftp: paramiko.SFTPClient,
    remote_folder: str,
) -> list[str]:
    """
    Search the remote host and return paths of files whose names contain
    one of the VIDEO_NAMES substrings AND whose extension is in
    VIDEO_EXTENSIONS.
    """
    log.info("Scanning remote directory: %s", remote_folder)
 
    transfer_list: list[str] = []
    names_lower = [name.lower() for name in VIDEO_NAMES]
 
    for remote_file in remote_walk(sftp, remote_folder):
        remote_path = PurePosixPath(remote_file)
        filename_lower = remote_path.name.lower()
        extension_lower = remote_path.suffix.lower()
 
        name_matches = any(name in filename_lower for name in names_lower)
        extension_matches = extension_lower in VIDEO_EXTENSIONS
 
        if name_matches and extension_matches:
            transfer_list.append(remote_file)
 
    log.info("Found %d matching file(s).", len(transfer_list))
    return transfer_list
 
 
# ---------------------------------------------------------------------------
# download_and_remove_files
# ---------------------------------------------------------------------------
 
def download_and_remove_files(
    sftp: paramiko.SFTPClient,
    transfer_list: list[str],
    remote_folder: str,
    destination: Path,
) -> None:
    """
    Download each remote video to the local destination using a safe
    .part pattern. The remote file is deleted only after the download
    passes size verification. The original directory structure is preserved.
    """
    destination.mkdir(parents=True, exist_ok=True)
 
    transferred = 0
    failed = 0
 
    for remote_file in transfer_list:
        remote_path = PurePosixPath(remote_file)
        relative_path = remote_path.relative_to(PurePosixPath(remote_folder))
        local_path = destination / Path(*relative_path.parts)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = Path(f"{local_path}.part")
 
        log.info("  Remote : %s", remote_file)
        log.info("  Local  : %s", local_path)
 
        try:
            # Capture remote size BEFORE starting the download.
            # If the recording process is still writing, we detect the
            # mismatch and do not delete the source.
            remote_size = sftp.stat(remote_file).st_size
 
            sftp.get(remote_file, str(temporary_path))
 
            if not temporary_path.exists():
                raise RuntimeError("Temporary download file was not created.")
 
            local_size = temporary_path.stat().st_size
 
            if local_size != remote_size:
                raise RuntimeError(
                    f"Size mismatch: remote={remote_size} bytes, "
                    f"local={local_size} bytes."
                )
 
            os.replace(temporary_path, local_path)
            sftp.remove(remote_file)
 
            transferred += 1
            log.info("  Status : moved successfully.\n")
 
        except Exception as exc:
            failed += 1
            log.error("  Status : transfer failed — %s", exc)
            log.error("           Source file was NOT deleted.\n")
            if temporary_path.exists():
                temporary_path.unlink()
 
    log.info("=" * 46)
    log.info("  Successfully moved : %d", transferred)
    log.info("  Failed             : %d", failed)
    log.info("=" * 46)
 
 
# ---------------------------------------------------------------------------
# connect_to_target
# ---------------------------------------------------------------------------
 
def connect_to_target(
    target: str,
    username: str,
    port: int,
) -> paramiko.SSHClient:
    """
    Open an SSH connection to the remote host.
 
    Uses RejectPolicy — the remote host key must already be in
    ~/.ssh/known_hosts. This prevents silent acceptance of unknown
    or changed host keys, which is important for a tool that deletes
    source files after transfer.
 
    To add a host to known_hosts:
        ssh-keyscan -H <target> >> ~/.ssh/known_hosts
    """
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
 
    # RejectPolicy: refuse connection if the host key is not already
    # known. Safer than AutoAddPolicy for a destructive transfer tool.
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
 
    password = getpass.getpass(f"SSH password for {username}@{target}: ")
 
    try:
        ssh.connect(
            hostname=target,
            port=port,
            username=username,
            password=password,
            timeout=20,
        )
    except paramiko.ssh_exception.NoValidConnectionsError as exc:
        log.error("Could not connect: %s", exc)
        sys.exit(1)
 
    return ssh
 
 
# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
 
def main() -> None:
    args = parse_args()
 
    target: str = args.target
    username: str = args.username
    remote_folder: str = args.remote.rstrip("/")   # normalise trailing slash
    destination: Path = Path(args.dest)
    port: int = args.port
 
    ssh: paramiko.SSHClient | None = None
    sftp: paramiko.SFTPClient | None = None
 
    try:
        log.info("Connecting to %s@%s:%d ...", username, target, port)
        ssh = connect_to_target(target, username, port)
        sftp = ssh.open_sftp()
 
        transfer_list = create_transfer_list(sftp, remote_folder)
 
        if not transfer_list:
            log.info("No matching videos found. Nothing to do.")
            return
 
        log.info("Files queued for transfer:")
        for f in transfer_list:
            log.info("  %s", f)
 
        download_and_remove_files(sftp, transfer_list, remote_folder, destination)
 
    except paramiko.AuthenticationException:
        log.error("SSH authentication failed.")
        sys.exit(1)
 
    except paramiko.SSHException as exc:
        log.error("SSH error: %s", exc)
        sys.exit(1)
 
    except FileNotFoundError as exc:
        log.error("Directory or file not found: %s", exc)
        sys.exit(1)
 
    except Exception as exc:
        log.error("Unexpected error: %s", exc)
        sys.exit(1)
 
    finally:
        if sftp is not None:
            sftp.close()
        if ssh is not None:
            ssh.close()
        log.info("Connection closed.")
 
 
if __name__ == "__main__":
    main()
 






