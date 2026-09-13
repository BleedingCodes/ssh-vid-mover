import getpass
import os
import stat
import paramiko
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# Configuration — edit these before running
# ---------------------------------------------------------------------------

TARGET = "192.168.1.105"          # Remote machine IP or hostname
USERNAME = "side"                  # SSH username on the remote machine
REMOTE_FOLDER = "/home/side/Python/Cam_System/recordings/"  # Remote directory to search
DESTINATION_DIRECTORY = Path("/media/fight/Tb/Downloaded_Recordings")  # Local destination

VIDEO_NAMES = (
    "d-link",
    "amcrestbullet",
)

# Set to True to print extra trace information for debugging.
DEBUG = False


# ---------------------------------------------------------------------------
# remote_walk
# ---------------------------------------------------------------------------

def remote_walk(sftp: paramiko.SFTPClient, remote_directory: str):
    """
    Recursively walk a directory on the remote host.
    Yields full remote file paths as strings.
    """
    if DEBUG:
        print(f"[DEBUG] Walking: {remote_directory}")

    for item in sftp.listdir_attr(remote_directory):
        remote_path = str(PurePosixPath(remote_directory) / item.filename)

        if stat.S_ISDIR(item.st_mode):
            yield from remote_walk(sftp, remote_path)
        elif stat.S_ISREG(item.st_mode):
            yield remote_path


# ---------------------------------------------------------------------------
# create_transfer_list
# ---------------------------------------------------------------------------

def create_transfer_list(sftp: paramiko.SFTPClient) -> list[str]:
    """
    Walk REMOTE_FOLDER and return a list of remote file paths whose
    filenames contain one of the substrings in VIDEO_NAMES (case-insensitive).
    """
    transfer_list: list[str] = []
    names_lower = [name.lower() for name in VIDEO_NAMES]

    for remote_file in remote_walk(sftp, REMOTE_FOLDER):
        remote_path = PurePosixPath(remote_file)
        filename_lower = remote_path.name.lower()

        if any(name in filename_lower for name in names_lower):
            transfer_list.append(remote_file)

    return transfer_list


# ---------------------------------------------------------------------------
# download_and_remove_files
# ---------------------------------------------------------------------------

def download_and_remove_files(
    sftp: paramiko.SFTPClient,
    transfer_list: list[str],
) -> None:
    """
    Download each remote video to DESTINATION_DIRECTORY, preserving the
    remote directory structure relative to REMOTE_FOLDER.

    Transfer sequence for each file:
        1. Download → .part temporary file
        2. Verify local size == remote size
        3. Rename .part → final filename
        4. Delete remote original

    On any failure the remote file is left untouched and the .part file
    is removed. The script continues to the next file.
    """
    DESTINATION_DIRECTORY.mkdir(parents=True, exist_ok=True)

    transferred = 0
    failed = 0

    for remote_file in transfer_list:
        remote_path = PurePosixPath(remote_file)
        relative_path = remote_path.relative_to(PurePosixPath(REMOTE_FOLDER))
        local_path = DESTINATION_DIRECTORY / Path(*relative_path.parts)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = Path(f"{local_path}.part")

        print()
        print(f"Target: {remote_file}")
        print(f"Host:   {local_path}")

        try:
            # Step 1 — download to .part file
            sftp.get(remote_file, str(temporary_path))

            # Step 2 — confirm the file was created locally
            if not temporary_path.exists():
                raise RuntimeError("Temporary download file was not created.")

            # Step 3 — verify size
            remote_size = sftp.stat(remote_file).st_size
            local_size = temporary_path.stat().st_size

            if local_size != remote_size:
                raise RuntimeError(
                    f"Size mismatch: remote={remote_size} bytes, "
                    f"local={local_size} bytes"
                )

            # Step 4 — finalize
            os.replace(temporary_path, local_path)

            # Step 5 — delete remote original
            sftp.remove(remote_file)

            transferred += 1
            print("Moved successfully.")

        except Exception as error:
            failed += 1
            print(f"Transfer failed: {error}")
            print("Remote file was not deleted.")

            if temporary_path.exists():
                temporary_path.unlink()

    print()
    print("----------------------------------------")
    print(f"Successfully moved: {transferred}")
    print(f"Failed:             {failed}")
    print("----------------------------------------")


# ---------------------------------------------------------------------------
# connect_to_target
# ---------------------------------------------------------------------------

def connect_to_target() -> paramiko.SSHClient:
    """
    Open an SSH connection to TARGET using password authentication.

    Host key policy: AutoAddPolicy is used, which silently accepts new host
    keys. This is convenient for home-lab use but means the connection is
    not protected against a first-use MITM attack. If you need stricter
    security, replace AutoAddPolicy with RejectPolicy and ensure the remote
    host is already in ~/.ssh/known_hosts before running.
    """
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    password = getpass.getpass(f"SSH password for {USERNAME}@{TARGET}: ")

    ssh.connect(
        hostname=TARGET,
        port=22,
        username=USERNAME,
        password=password,
        timeout=20,
    )

    return ssh


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ssh = None
    sftp = None

    try:
        print(f"Connecting to {USERNAME}@{TARGET}...")

        ssh = connect_to_target()
        sftp = ssh.open_sftp()

        print(f"\nSearching target directory:\n{REMOTE_FOLDER}\n")

        transfer_list = create_transfer_list(sftp)

        if not transfer_list:
            print("No matching videos were found.")
            return

        print(f"Found {len(transfer_list)} matching video(s):")
        for remote_file in transfer_list:
            print(f"  {remote_file}")

        download_and_remove_files(sftp, transfer_list)

    except paramiko.AuthenticationException:
        print("SSH authentication failed.")

    except paramiko.SSHException as error:
        print(f"SSH error: {error}")

    except FileNotFoundError as error:
        print(f"Directory or file not found: {error}")

    except Exception as error:
        print(f"Unexpected error: {error}")

    finally:
        if sftp is not None:
            sftp.close()
        if ssh is not None:
            ssh.close()


if __name__ == "__main__":
    main()
