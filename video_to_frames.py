#!/usr/bin/env python3
"""
Video Frame Extractor
Reads a video stream and writes out each frame as a PNG file.

API References:
--------------
OpenCV (cv2) - Computer Vision Library
Documentation: https://docs.opencv.org/4.x/

Key APIs used:
1. cv2.VideoCapture - Capture video from file or camera
   https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html

2. cv2.CAP_PROP_* - Video property constants
   https://docs.opencv.org/4.x/d4/d15/group__videoio__flags__base.html

3. cv2.imwrite - Save image to file
   https://docs.opencv.org/4.x/d4/da8/group__imgcodecs.html#gabbc7ef1aa2edfaa87772f1202d67e0ce

Installation:
------------
pip install opencv-python
"""

import cv2  # OpenCV library for video processing
import os
import sys
import argparse
from pathlib import Path


def extract_frames(video_source, output_dir="frames", Callback=None, frame_prefix="frame", skip_frames=0):
    """
    Extract frames from a video stream and save as PNG files.
    
    Args:
        video_source: Path to video file or camera index (0 for default webcam)
        output_dir: Directory to save frames
        frame_prefix: Prefix for frame filenames
        skip_frames: Number of frames to skip between saves (0 = save all frames)
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    try:
        # We do this to remove any old junk that may have been in the directory
        os.remove(os.path.join(output_dir, "fps.txt"))
    except FileNotFoundError:
        pass

    
    # API: cv2.VideoCapture(source)
    # Opens a video file or camera stream for reading
    # source can be: filename (str), camera index (int), or URL
    cap = cv2.VideoCapture(video_source)
    
    # API: VideoCapture.isOpened()
    # Returns True if video capturing has been initialized successfully
    if not cap.isOpened():
        print(f"Error: Could not open video source: {video_source}")
        return
    
    # API: VideoCapture.get(propId)
    # Get video properties using property constants
    
    # cv2.CAP_PROP_FPS - Frame rate (frames per second)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # cv2.CAP_PROP_FRAME_COUNT - Total number of frames in the video
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # cv2.CAP_PROP_FRAME_WIDTH - Width of frames in pixels
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    
    # cv2.CAP_PROP_FRAME_HEIGHT - Height of frames in pixels
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video properties:")
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS: {fps}")
    print(f"  Total frames: {total_frames if total_frames > 0 else 'N/A (live stream)'}")
    print(f"  Output directory: {output_dir}")
    print(f"  Skip frames: {skip_frames}")
    print()
    if Callback is not None:
        Callback(1, f'Resolution {width}x{height} Frames {total_frames} FPS: {fps}')
    
    frame_count = 0
    saved_count = 0
    
    try:
        while True:
            # API: VideoCapture.read()
            # Grabs, decodes and returns the next video frame
            # Returns: (ret, frame) where ret is boolean success flag
            # and frame is the image array (numpy ndarray)
            ret, frame = cap.read()
            
            # Break if no frame is returned (end of video)
            if not ret:
                break
            
            # Save frame if it's time (based on skip_frames)
            if frame_count % (skip_frames + 1) == 0:
                # Generate filename with zero-padded number
                filename = f"{frame_prefix}_{saved_count:06d}.png"
                filepath = os.path.join(output_dir, filename)
                
                # API: cv2.imwrite(filename, img, [params])
                # Saves an image to a specified file
                # The image format is chosen based on the filename extension
                # Returns True if the image is successfully saved
                cv2.imwrite(filepath, frame)
                saved_count += 1
                
                # Print progress every 10 saved frames
                if saved_count % 10 == 0:
                    if (Callback is not None):
                        Callback(2, f"Frames {saved_count} / {total_frames}")
            
            frame_count += 1
        SpeedFile = open(os.path.join(output_dir, "fps.txt"), "w")
        print(fps, file=SpeedFile)
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(8)
    
    finally:
        # API: VideoCapture.release()
        # Closes video file or capturing device
        # Releases all resources allocated by VideoCapture
        cap.release()
        print(f"\nExtraction complete!")
        print(f"Total frames processed: {frame_count}")
        print(f"Total frames saved: {saved_count}")
        print(f"Frames saved to: {os.path.abspath(output_dir)}")

def main():
    parser = argparse.ArgumentParser(
        description="Extract frames from a video stream and save as PNG files"
    )
    parser.add_argument(
        "video_source",
        help="Path to video file or camera index (0 for default webcam)"
    )
    parser.add_argument(
        "-o", "--output",
        default="frames",
        help="Output directory for frames (default: frames)"
    )
    parser.add_argument(
        "-p", "--prefix",
        default="frame",
        help="Prefix for frame filenames (default: frame)"
    )
    parser.add_argument(
        "-s", "--skip",
        type=int,
        default=0,
        help="Number of frames to skip between saves (default: 0, save all frames)"
    )
    
    args = parser.parse_args()
    
    # Convert video_source to int if it's a digit (camera index)
    video_source = args.video_source
    if video_source.isdigit():
        video_source = int(video_source)
    
    extract_frames(video_source, args.output, None, args.prefix, args.skip)


if __name__ == "__main__":
    main()
