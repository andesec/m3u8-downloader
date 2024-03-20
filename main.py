import os
import tempfile
import csv
import m3u8
import requests
import time
import argparse
import subprocess
import re

from urllib.parse import urljoin
from datetime import datetime
from tqdm import tqdm


def download_m3u8_video(url, output_file, playlist_index):
    # Parse the m3u8 file
    m3u8_obj = m3u8.load(url)

    # Create a temporary directory to store the segments
    with tempfile.TemporaryDirectory() as temp_dir:

        download_start_time = time.time()
        m3u8_playlist_segments = m3u8_obj.segments

        # Check if the m3u8 file is a master playlist
        if m3u8_obj.is_variant:
            # Get the selected variant playlist
            playlist_url = urljoin(url, m3u8_obj.playlists[playlist_index].uri)
            playlist_obj = m3u8.load(playlist_url)
            m3u8_playlist_segments = playlist_obj.segments

        # Download the segments and find out the total duration too.
        segments, total_duration = download_segments(
            m3u8_playlist_segments,
            playlist_url if m3u8_obj.is_variant else url,
            temp_dir
        )

        # Create a text file listing the segments
        list_file = os.path.join(temp_dir, 'list.txt')

        with open(list_file, 'w') as f:
            for segment in segments:
                f.write(f"file '{segment}'\n")

        download_subtitle(m3u8_obj, url, output_file)

        download_end_time = time.time()
        print_and_log("Time taken to download segments: {}", download_end_time - download_start_time)

        write_video(list_file, output_file, total_duration)


def download_segments(m3u8_segments, url, temp_dir):
    segments = []
    total_duration = 0

    for segment in tqdm(m3u8_segments, desc="Downloading segments", unit="segment"):
        segment_url = urljoin(url, segment.uri)
        response = requests.get(segment_url, stream=True)

        if response.status_code != 200:
            print_and_log(f"Failed to download segment: {segment_url}")
            continue

        segment_file = os.path.join(temp_dir, segment.uri.split('/')[-1])
        segments.append(segment_file)

        total_duration += segment.duration

        with open(segment_file, 'wb') as segment_file_pointer:
            segment_file_pointer.write(response.content)

    print_and_log(f"Number of segments downloaded: {len(segments)}")
    print_and_log("Total duration is {}", total_duration)
    return segments, total_duration


def download_subtitle(m3u8_obj, url, output_file):
    if not m3u8_obj.media:
        print_and_log("No subtitle streams found")
        return

    # Download subtitle streams
    subtitles = []

    for media in m3u8_obj.media:

        if media.type == 'SUBTITLES':
            subtitle_url = urljoin(url, media.uri)
            response = requests.get(subtitle_url, stream=True)

            if response.status_code != 200:
                print_and_log(f"Failed to download subtitle: {subtitle_url}")
                continue

            subtitle_file = os.path.join(os.path.dirname(output_file), media.uri.split('/')[-1])
            subtitles.append(subtitle_file)

            with open(subtitle_file, 'wb') as f:
                f.write(response.content)


def write_video(input_file, output_file, total_duration):
    ffmpeg_start_time = time.time()

    # Run FFmpeg and parse its output
    process = subprocess.Popen(
        ["ffmpeg", "-f", "concat", "-safe", "0", "-i", input_file, "-c", "copy", output_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )

    progress_bar = tqdm(total=total_duration, unit='s', ncols=70, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}')

    for line in process.stdout:
        # Update the progress bar
        match = re.search(r"time=(\d+:\d+:\d+\.\d+)", line)
        if match is not None:
            process_time = sum(float(x) * 60 ** i for i, x in enumerate(reversed(match.group(1).split(":"))))
            progress_bar.update(process_time - progress_bar.n)

    progress_bar.close()

    ffmpeg_end_time = time.time()
    print_and_log("Time taken for ffmpeg to process: {}", ffmpeg_end_time - ffmpeg_start_time)


def print_and_log(message, time_taken=None):
    if time_taken is not None:
        minutes, seconds = divmod(time_taken, 60)
        readable_time = f"{int(minutes)} minutes and {int(seconds)} seconds"
        message = message.format(readable_time)

    print(message)
    print(os.linesep)

    with open(log_filepath, 'a') as log_file:
        log_file.write(message)
        log_file.write("\n")
        log_file.write("\n")


log_filepath = "log_{}".format(time.time())

if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Download videos from a CSV file.')
    parser.add_argument('csv_filepath', help='The filepath of the CSV file.')
    parser.add_argument('--output_dir', help='The directory where the output file should be saved.')
    parser.add_argument('--playlist_index', type=int, default=0, help='The index of the playlist to use.')
    parser.add_argument('--output-extension', type=str, default='mp4', help='The extension or format for this video.')

    # Parse the command-line arguments
    args = parser.parse_args()

    # Provide the filepath for the CSV file
    csv_filepath = args.csv_filepath
    ext = args.output_extension

    # Parse the CSV filename and create necessary directories
    filename = os.path.basename(csv_filepath)
    first_part, second_part, *_ = filename.split('-')

    output_dir = args.output_dir
    if output_dir is None:
        with open('default_output_path.txt', 'r') as f:
            output_dir = f.read().strip()

    # Ensure the output directory exists
    # os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, first_part, second_part), exist_ok=True)

    print_and_log(f"Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Parse the CSV file and download the videos
    with open(f"csv/{csv_filepath}", 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            # Skip any row that doesn't have value in first or second column
            if not row or len(row) < 2 or not row[0] or not row[1]:
                print_and_log(f"Invalid row: {row}")
                continue

            # Create the output filepath
            output_filename = os.path.join(output_dir, first_part, second_part, f"{row[0]}.{ext}")
            print_and_log(f"Downloading {row[0]} video to: {output_filename}")

            # Get the m3u8 URL
            m3u8_url = row[1]

            # Download the video and save it to the output file
            start_time = time.time()

            try:
                download_m3u8_video(
                    m3u8_url,
                    output_filename,
                    args.playlist_index  # Change the last parameter to select the playlist
                )
            except Exception as e:
                print_and_log(f"Failed to download video {row[0]}: {e}")
                continue

            end_time = time.time()
            print_and_log("Time taken to download and process: {}", end_time - start_time)

    print_and_log("Videos downloaded successfully!")
