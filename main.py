import os
import tempfile
import csv
import ffmpeg
import m3u8
import requests
import time
import argparse

from urllib.parse import urljoin
from datetime import datetime


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

        # Download the segments
        segments = download_segments(m3u8_playlist_segments, playlist_url if m3u8_obj.is_variant else url, temp_dir)

        # Create a text file listing the segments
        list_file = os.path.join(temp_dir, 'list.txt')

        with open(list_file, 'w') as f:
            for segment in segments:
                f.write(f"file '{segment}'\n")

        download_subtitle(m3u8_obj, url, output_file)

        download_end_time = time.time()
        print_and_log(f"Time taken to download segments: {download_end_time - download_start_time} seconds")

        write_video(list_file, output_file)


def download_segments(m3u8_segments, url, temp_dir):
    counter = 1
    segments = []

    for segment in m3u8_segments:

        segment_url = urljoin(url, segment.uri)
        response = requests.get(segment_url, stream=True)

        if response.status_code != 200:
            print_and_log(f"Failed to download segment: {segment_url}")
            continue

        segment_file = os.path.join(temp_dir, segment.uri.split('/')[-1])
        segments.append(segment_file)

        with open(segment_file, 'wb') as f:
            f.write(response.content)

        counter += 1

    print_and_log(f"Number of segments downloaded: {counter}")
    return segments


def download_subtitle(m3u8_obj, url, output_file):
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


def write_video(list_file, output_file):
    import subprocess

    ffmpeg_start_time = time.time()

    # command = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file, '-loglevel', 'quiet', output_file]

    # with open('ffmpeg_log.txt', 'w') as f:
    #     subprocess.run(command, stdout=f, stderr=f)

    # Combine all the segments into a single video file
    ffmpeg.input(list_file, format='concat', safe=0).output(output_file).run()

    ffmpeg_end_time = time.time()
    print_and_log(f"Time taken for ffmpeg to process: {ffmpeg_end_time - ffmpeg_start_time} seconds")


def print_and_log(message):
    print(message)
    print(os.linesep)

    log_file = open('log.txt', 'a')
    log_file.write(message + os.linesep)


if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Download videos from a CSV file.')
    parser.add_argument('csv_filepath', help='The filepath of the CSV file.')

    # Parse the command-line arguments
    args = parser.parse_args()

    # Provide the filepath for the CSV file
    csv_filepath = args.csv_filepath

    # Parse the CSV filename and create necessary directories
    filename = os.path.basename(csv_filepath)
    first_part, second_part, *_ = filename.split('-')
    os.makedirs(os.path.join(first_part, second_part), exist_ok=True)

    print_and_log(f"Current date and time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Parse the CSV file and download the videos
    with open(csv_filepath, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            # Skip any row that doesn't have value in first or second column
            if not row or len(row) < 2 or not row[0] or not row[1]:
                print_and_log(f"Invalid row: {row}")
                continue

            # Create the output filepath
            output_filename = os.path.join(first_part, second_part, f"{row[0]}.mp4")
            print_and_log(f"Downloading video to: {output_filename}")

            # Get the m3u8 URL
            m3u8_url = row[1]

            print_and_log(f"Downloading {row[0]}")

            # Download the video and save it to the output file
            start_time = time.time()

            download_m3u8_video(m3u8_url, output_filename, 0)  # Change the last parameter to select the playlist

            end_time = time.time()
            print_and_log(f"Time taken to download and process: {end_time - start_time} seconds")

    print_and_log("Videos downloaded successfully!")
