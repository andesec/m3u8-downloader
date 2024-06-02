import os
import tempfile
import csv
import m3u8
import requests
import time
import argparse
import subprocess
import re
import glob

from urllib.parse import urljoin
from datetime import datetime
from tqdm import tqdm


def download_m3u8_video(url, output_file, playlist_index, is_quality_check_only, is_sleep_disabled):
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
            temp_dir,
            is_quality_check_only,
            is_sleep_disabled
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


def download_segments(m3u8_segments, url, temp_dir, is_quality_check_only, is_sleep_disabled):
    segments = []
    total_duration = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/58.0.3029.110 Safari/537.3",
        "Referer": "https://vidplay.online/",
        "Connection": "keep-alive",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
    }

    for segment in tqdm(m3u8_segments, desc="Downloading segments", unit="segment"):
        segment_url = urljoin(url, segment.uri)
        response = requests.get(segment_url, stream=True, headers=headers)

        if response.status_code != 200:
            print_and_log(f"Failed to download segment: {segment_url}")
            continue

        segment_file = os.path.join(temp_dir, segment.uri.split('/')[-1])
        segments.append(segment_file)

        total_duration += segment.duration

        with open(segment_file, 'wb') as segment_file_pointer:
            segment_file_pointer.write(response.content)

        # A tricky way to prevent the server from blocking requests
        if len(segments) % 2 == 0 and is_sleep_disabled is False:
            time.sleep(1)  # Wait for 1 second before downloading the next segment

        # Break because we only want a sample for testing
        if total_duration > 300 and is_quality_check_only is True:
            break

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

    # create file if it doesn't exist
    if not os.path.exists(ffmpeg_log_filepath):
        open(ffmpeg_log_filepath, 'w').close()

    with open(ffmpeg_log_filepath, 'a') as log_file:
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-analyzeduration", "10000000",
                "-probesize", "10000000",
                "-f", "concat",
                "-safe", "0",
                "-i", input_file,
                "-c", "copy",
                output_file
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        progress_bar = tqdm(total=total_duration, unit='s', ncols=70, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}')

        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                log_file.write(output)
                match = re.search(r"time=(\d+:\d+:\d+\.\d+)", output)
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

    # create file if it doesn't exist
    if not os.path.exists(std_log_filepath):
        open(std_log_filepath, 'w').close()

    with open(std_log_filepath, 'a') as log_file:
        log_file.write(message)
        log_file.write("\n")
        log_file.write("\n")


std_log_filepath = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'logs',
    f"process_{datetime.now().strftime('%Y%m%d_%H_%M_%S')}.log"
)

ffmpeg_log_filepath = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'logs',
    f"ffmpeg_{datetime.now().strftime('%Y%m%d_%H_%M_%S')}.log"
)

csv_dir_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'csv'
)


def parse_args():
    parser = argparse.ArgumentParser(description='Download videos from a CSV file.')
    parser.add_argument('--csv_filepath', help='The filepath of the CSV file.')
    parser.add_argument('--output_dir', help='The directory where the output file should be saved.')
    parser.add_argument('--playlist_index', type=int, default=0, help='The index of the playlist to use.')
    parser.add_argument('--output-extension', type=str, default='mp4',
                        help='The extension or format for this video.')
    parser.add_argument('--quality-check-only', type=bool, default=False,
                        help='Whether to download full videos or just run a quality check for first file.')
    parser.add_argument('--skip-sleep', type=bool, default=False,
                        help='Keep downloading segments without waiting, this might cause the server to block you.')
    return parser.parse_args()


def setup_directories(args, selected_csv_filepath):
    filename = os.path.basename(selected_csv_filepath)
    first_part, second_part, *_ = filename.split('-')
    output_dir = args.output_dir

    if output_dir is None:
        with open('default_output_path.txt', 'r') as f:
            output_dir = f.read().strip()

    final_output_dir = os.path.join(
        output_dir,
        first_part,
        second_part,
        'sample' if args.quality_check_only is True else ''
    )
    os.makedirs(final_output_dir, exist_ok=True)
    return final_output_dir


def select_csv(args):
    csv_filepath = args.csv_filepath
    if csv_filepath is not None:
        return csv_filepath

    csv_files = glob.glob('csv/*.csv')
    for i, csv_file in enumerate(csv_files, start=1):
        print(f"{i}: {csv_file}")

    while True:
        selection = input("Enter the number of the CSV file to process: ")
        if selection.isdigit() and 1 <= int(selection) <= len(csv_files):
            return csv_files[int(selection) - 1]
        else:
            print("Invalid selection. Please try again.")


def process_selected_csv(args, output_dir, csv_filepath):
    counter = 1

    with open(csv_filepath, 'r') as f:
        reader = csv.reader(f)

        for row in reader:

            if not row or len(row) < 2 or not row[0] or not row[1]:
                print_and_log(f"Invalid row: {row}")
                continue

            output_filename = os.path.join(output_dir, f"{row[0]}.{args.output_extension}")
            print_and_log(f"Downloading {row[0]} video to: {output_filename}")
            m3u8_url = row[1]

            # check if the output_filename already exists with extension mp4 or mkv, if yes then skip:
            if os.path.exists(output_filename) or os.path.exists(
                    output_filename.replace('.mkv', '.mp4')) or os.path.exists(output_filename.replace('.mp4', '.mkv')):
                print_and_log(f"File already exists: {output_filename}")
                continue

            start_time = time.time()

            try:
                download_m3u8_video(m3u8_url, output_filename, args.playlist_index, args.quality_check_only,
                                    args.skip_sleep)
            except Exception as e:
                print_and_log(f"Failed to download video {row[0]}: {e}")
                continue

            end_time = time.time()
            print_and_log("Time taken to download and process: {}", end_time - start_time)
            print_and_log("----------------------------------------------------")

            counter += 1

            if args.quality_check_only is True and counter == 2:
                break


if __name__ == "__main__":
    args = parse_args()
    selected_csv_filepath = select_csv(args)
    output_dir = setup_directories(args, selected_csv_filepath)

    print_and_log(f"Process started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_and_log(f"CSV file: {selected_csv_filepath}")
    print_and_log(f"Output directory: {output_dir}")
    print_and_log(f"Playlist index: {args.playlist_index}")
    print_and_log(f"Standard log file: {std_log_filepath}")
    print_and_log(f"FFmpeg log file: {ffmpeg_log_filepath}")
    print_and_log(f"Output extension: {args.output_extension}")
    print_and_log(f"Quality check only: -- {args.quality_check_only} --")
    print_and_log(f"Skip sleep: -- {args.skip_sleep} --")
    print_and_log("----------------------------------------------------")

    process_selected_csv(args, output_dir, selected_csv_filepath)
    print_and_log("Videos downloaded successfully!")
    print_and_log(f"Process ended at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
