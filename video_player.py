import os
import platform
import subprocess
import sys

def play_video(video_path):
    """
    Play a video file using the default or available video player based on the operating system.
    
    Args:
        video_path (str): Path to the video file to be played
    
    Returns:
        bool: True if video player was launched successfully, False otherwise
    """
    # Check if the video file exists
    if not os.path.isfile(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        return False
    
    # Detect the operating system
    operating_system = platform.system()
    
    try:
        if operating_system == "Windows":
            # Windows: Use PowerShell's Start-Process to launch default video player
            # Note: Not all Windows video players support loop flags
            Process = subprocess.Popen(
                ['powershell', '-command', f'Start-Process "{self.video_path}"'],
                shell=True,
                stdout=subprocess.DEVNULL,  # Suppress output
                stderr=subprocess.DEVNULL
            )
            return (Process)
        
        elif operating_system == "Darwin":  # macOS
            # Try to use QuickTime Player first, fall back to 'open' command
            try:
                Process = subprocess.Popen(['open', '-a', 'QuickTime Player', video_path])
            except:
                Process = subprocess.Popen(['open', video_path])
            return (Process)
        
        elif operating_system == "Linux":
            # Try common Linux video players in order of preference
            linux_players = [
                ['vlc', video_path],
                ['mpv', video_path],
                ['mplayer', video_path],
                ['xdg-open', video_path]  # Generic file opener as fallback
            ]
            
            for player in linux_players:
                try:
                    Process = subprocess.Popen(player)
                    return (Process)
                except FileNotFoundError:
                    continue
            else:
                # If no player was found
                print("Error: No suitable video player found on this Linux system.")
                print("Please install one of: vlc, mpv, mplayer, or set a default application with xdg-mime.")
                sys.exit(8)
        
        else:
            print(f"Error: Unsupported operating system: {operating_system}")
            sys.exit(8)
            
    except Exception as e:
        print(f"Error playing video: {e}")
        sys.exit(8)

if __name__ == "__main__":
    # Check if a video file was provided as argument
    if len(sys.argv) < 2:
        print("Usage: python video_player.py <path_to_video_file>")
        sys.exit(1)
    
    video_path = sys.argv[1]
    success = play_video(video_path)
    
    if not success:
        sys.exit(1)
