import os
import platform
import subprocess
import sys
import threading


def _reap(process):
    """Wait for *process* to exit in a background thread so it is never a zombie."""
    process.wait()


def play_video(video_path):
    """
    Play a video file using the default or available video player based on the operating system.

    Launches the video player in the background and returns immediately. A daemon
    thread waits on the player process so that it is reaped when it exits and never
    becomes a zombie.

    Args:
        video_path (str): Path to the video file to be played

    Returns:
        Popen process object or none if something went wrong
    """
    # Check if the video file exists
    if not os.path.isfile(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        return False

    # Detect the operating system
    operating_system = platform.system()

    try:
        if operating_system == "Windows":
            # Windows: Use PowerShell's Start-Process to launch the default video player.
            # Pass the command as a single string when shell=True.
            process = subprocess.Popen(
                f'Start-Process "{video_path}"',
                shell=True,
                executable="powershell",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            threading.Thread(target=_reap, args=(process,), daemon=True).start()
            return process

        elif operating_system == "Darwin":  # macOS
            # Try QuickTime Player first, fall back to the generic 'open' command.
            try:
                process = subprocess.Popen(["open", "-a", "QuickTime Player", video_path])
            except Exception:
                process = subprocess.Popen(["open", video_path])
            threading.Thread(target=_reap, args=(process,), daemon=True).start()
            return process

        elif operating_system == "Linux":
            # Try common Linux video players in order of preference.
            linux_players = [
                ["cvlc", "--no-qt-privacy-ask", "--play-and-exit", "--fullscreen", video_path],
                ["mpv", video_path],
                ["mplayer", video_path],
            ]

            for player_cmd in linux_players:
                try:
                    process = subprocess.Popen(player_cmd)
                    threading.Thread(target=_reap, args=(process,), daemon=True).start()
                    return process
                except FileNotFoundError:
                    # This player isn't installed; try the next one.
                    continue

            # Reached only if no player was found.
            print("Error: No suitable video player found on this Linux system.")
            print("Please install one of: vlc, mpv, or mplayer.")
            return None

        else:
            print(f"Error: Unsupported operating system: {operating_system}")
            return None

    except Exception as e:
        print(f"Error playing video: {e}")
        return None


if __name__ == "__main__":
    # Check if a video file was provided as argument
    if len(sys.argv) < 2:
        print("Usage: python video_player.py <path_to_video_file>")
        sys.exit(1)

    video_path = sys.argv[1]
    success = play_video(video_path)

    if not success:
        sys.exit(1)
