import getpass
import os
import stat
import paramiko
from pathlib import Path, PurePosixPath

TARGET = "192.168.1.105"
USERNAME = "side"
REMOTE_FOLDER = ("/home/side/Python/Cam_System/recordings/")
DESTINATION_DIRECTORY = Path("/media/fight/Tb/Downloaded_Recordings")

VIDEO_NAMES = (
    "d-link",
    "amcrestbullet",
)



# ----------------------------remote_walk Function---------------------------------------------------------------------------------------------------------------

def remote_walk(sftp, remote_directory):
    print("-----------  Running remote_walk function  ------------ \n")
    count = 0
    print(count)
    """
    Recursively search a directory on the target computer.
    Yields full remote file paths.
    """
    for item in sftp.listdir_attr(remote_directory):
        
        remote_path = str(
            PurePosixPath(remote_directory) / item.filename
        )
        count =+1
        if stat.S_ISDIR(item.st_mode):

            yield from remote_walk(sftp, remote_path)
        elif stat.S_ISREG(item.st_mode):
            yield remote_path
    print("----------  End of remote_walk function  ------------\n")

# ----------------------------create_transfer_list Function---------------------------------------------------------------------------------------------------------------

def create_transfer_list(sftp):
    print("-----------  Running create_transfer_list function  ------------ \n")

    """
    Search the target computer and return videos whose filenames
    contain one of the names in VIDEO_NAMES.
    """

    transfer_list = []

    names_lower = [
        name.lower()
        for name in VIDEO_NAMES
    ]

    for remote_file in remote_walk(
        sftp,
        REMOTE_FOLDER,
    ):
        remote_path = PurePosixPath(remote_file)
        filename_lower = remote_path.name.lower()

        name_matches = any(
            name in filename_lower
            for name in names_lower
        )

        if name_matches:
            transfer_list.append(remote_file)
    print("----------  End of create_transfer_list function  ------------\n")

    return transfer_list


# ----------------------------download_and_remove_files Function---------------------------------------------------------------------------------------------------------------

def download_and_remove_files(sftp, transfer_list):
    print("-----------  Running download_and_remove_files function  ------------ \n")

    """
    Download each remote video to the host.

    The remote file is deleted only after the download succeeds.
    The original directory structure is preserved.
    """

    DESTINATION_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    transferred = 0
    failed = 0

    for remote_file in transfer_list:
        remote_path = PurePosixPath(remote_file)

        relative_path = remote_path.relative_to(
            PurePosixPath(REMOTE_FOLDER)
        )

        local_path = (
            DESTINATION_DIRECTORY
            / Path(*relative_path.parts)
        )

        local_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = Path(
            f"{local_path}.part"
        )

        print()
        print(f"Target: {remote_file}")
        print(f"Host:   {local_path}")

        try:
            # Download to a temporary file first.
            sftp.get(
                remote_file,
                str(temporary_path),
            )

            # Confirm that something was downloaded.
            if not temporary_path.exists():
                raise RuntimeError(
                    "Temporary download file was not created."
                )

            remote_size = sftp.stat(remote_file).st_size
            local_size = temporary_path.stat().st_size

            if local_size != remote_size:
                raise RuntimeError(
                    f"Size mismatch: target={remote_size}, "
                    f"host={local_size}"
                )

            # Rename the completed download.
            os.replace(
                temporary_path,
                local_path,
            )

            # Remove original from the target.
            sftp.remove(remote_file)

            transferred += 1

            print("Moved successfully.")

        except Exception as error:
            failed += 1

            print(f"Transfer failed: {error}")
            print("Original target file was not deleted.")

            if temporary_path.exists():
                temporary_path.unlink()

    print()
    print("----------------------------------------")
    print(f"Successfully moved: {transferred}")
    print(f"Failed:             {failed}")
    print("----------------------------------------")
    print("----------  End of download_and_remove_files function  ------------\n")

# ----------------------------connect_to_target Function---------------------------------------------------------------------------------------------------------------

def connect_to_target():
    print("-----------  Running connect_to_target function  ------------ \n")

    """
    Connect from the host computer to the target computer.
    """

    ssh = paramiko.SSHClient()

    ssh.load_system_host_keys()

    # Allows the first connection when the target is not already
    # in ~/.ssh/known_hosts.
    ssh.set_missing_host_key_policy(
        paramiko.AutoAddPolicy()
    )

    password = getpass.getpass(
        f"SSH password for {USERNAME}@{TARGET}: "
    )

    ssh.connect(
        hostname=TARGET,
        port= 22,
        username=USERNAME,
        password=password,
        timeout=20,
    )
    print("----------  End of connect_to_target function  ------------\n")

    return ssh

# ----------------------------main Function---------------------------------------------------------------------------------------------------------------

def main():
    print("-----------  Running main function  ------------ \n")

    ssh = None
    sftp = None

    try:
        print(
            f"Connecting to "
            f"{USERNAME}@{TARGET}..."
        )

        ssh = connect_to_target()
        sftp = ssh.open_sftp()

        print(
            f"Searching target directory:\n"
            f"{REMOTE_FOLDER}"
        )

        transfer_list = create_transfer_list(sftp)

        if not transfer_list:
            print()
            print(
                "No matching videos were found."
            )
            return

        print()
        print(
            f"Found {len(transfer_list)} matching video(s):"
        )

        for remote_file in transfer_list:
            print(f"  {remote_file}")

        download_and_remove_files(
            sftp,
            transfer_list,
        )

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

    print("----------  End of main function  ------------\n")

if __name__ == "__main__":
    main()


