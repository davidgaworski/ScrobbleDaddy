import pygame
import numpy as np
import pyaudio
import asyncio
from shazamio import Shazam
import requests
import os
import json
import threading
import sounddevice as sd
import soundfile as sf
import pylast
import time
import datetime


# Load configuration from a JSON file
def load_config():
    dir_path = os.getcwd()
    config_path = os.path.join(dir_path, 'config.json')
    with open(config_path, 'r') as config_file:
        return json.load(config_file)

config = load_config()

# Initialize Pygame
pygame.init()

running = True

# Define screen dimensions
WIDTH = config['gui']['screen_width']
HEIGHT = config['gui']['screen_height']
NUM_BARS = 200  # 31 frequency bands
BAR_WIDTH = (WIDTH - 200) // NUM_BARS  # Adjust width based on image and text space

last_track_title = ""
last_artist_name = ""
last_track_play_count = 0
last_cover_art_url = ""

# Set up the display
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)

# Load the image
image_path = "image.jpg"  # Replace with your image file path

# Set up font for text
font = pygame.font.SysFont("Arial", 24)

chunk_size = 30
track_start_index = 0
artist_start_index = 0

p = pyaudio.PyAudio()

# Open the audio stream for input
stream = p.open(format=pyaudio.paInt16, channels=1,rate=config['audio']['sample_rate'], input=True, frames_per_buffer=config['audio']['chunk_size'])

# Set environment variable for ALSA
os.environ['PA_ALSA_PLUGHW'] = '1'

network = pylast.LastFMNetwork(
    api_key=config['lastfm']['api_key'],
    api_secret=config['lastfm']['api_secret'],
    username=config['lastfm']['username'],
    password_hash=pylast.md5(config['lastfm']['password']),
)

duration = 10  # seconds

isRecording = False

def record_audio():
    samplerate = 44100  # Hertz
    filename = 'output.wav'

    isRecording = True
    mydata = sd.rec(int(samplerate * config['audio']['record_seconds']), samplerate=44100,
                    channels=1, blocking=True)

    sf.write(filename, mydata, samplerate)

    isRecording = False
    return filename

async def recognize_song(wav_file):
    shazam = Shazam()

    try:
        return await shazam.recognize_song("output.wav")
    except Exception as e:
        pass
    return None

def song_play_count(result):
    global last_track_play_count

    track_title = result['track']['title']
    artist_name = result['track']['subtitle']

    track = pylast.Track(
        artist=artist_name, title=track_title, network=network, username=config["lastfm"]["username"]
    )

    # Act
    try:
        last_track_play_count = track.get_userplaycount()
    except Exception as e:
        pass
    print(last_track_play_count, "playcount")

def scrobbleMeDaddy(result):
    # Scrobble a track
    title = result['track']['title']
    artist = result['track']['subtitle']
    album = result['track']['sections'][0]['metadata'][0]['text']
    unix_timestamp = 0  # Unix timestamp of when the track started playing
    # Validate
    if unix_timestamp == 0:
        # Get UNIX timestamp
        unix_timestamp = int(time.mktime(datetime.datetime.now().timetuple()))
    print("Timestamp:\t" + str(unix_timestamp))

    network.scrobble(artist=artist, title=title, timestamp=unix_timestamp)

def update_gui(result):
    global last_track_title, last_artist_name, last_cover_art_url

    if 'track' in result:
        track_title = result['track']['title']
        artist_name = result['track']['subtitle']
        print(track_title, artist_name)
        cover_art_url = result['track']['images']['coverarthq'] if 'images' in result['track'] else None
        if (track_title != last_track_title or artist_name != last_artist_name or cover_art_url != last_cover_art_url):
            last_track_title = track_title
            last_artist_name = artist_name
            last_cover_art_url = cover_art_url

            if cover_art_url:
                response = requests.get(cover_art_url, timeout=config['network']['timeout'])
                image_data = response.content
                with open('image.jpg', 'wb') as f:
                    f.write(image_data)

            scrobbleMeDaddy(result)
            song_play_count(result)
            print(last_track_title, last_artist_name)


        else:

            print("No changes detected, skipping GUI update.")
    else:
        print("Could not recognize the song.")

async def update_song_information():
    wav_file = record_audio()
    if wav_file is not None:
        result = await recognize_song(wav_file)
        if result:
            print("got it")
            update_gui(result)
    else:
        # Ensure the GUI updates even if audio recognition fails
        root.after(config['gui']['update_interval'], lambda: asyncio.run(update_song_information()))

def run_recognition_loop():
    while True:
        asyncio.run(update_song_information())

def start_recognition_thread():
    thread = threading.Thread(target=run_recognition_loop)
    thread.daemon = True
    thread.start()

# Function to get frequency bands from audio data
def get_frequency_bands():
    # Read a chunk of audio data
    data = np.frombuffer(stream.read(config['audio']['chunk_size'], exception_on_overflow=False), dtype=np.int16)

    # Perform FFT on the audio data
    fft_data = np.fft.fft(data)

    # Get the magnitudes of the FFT result (abs value of the complex numbers)
    magnitudes = np.abs(fft_data)

    # Calculate frequency bins
    freqs = np.fft.fftfreq(len(data), 1 / config['audio']['sample_rate'])

    # Split the frequency spectrum into 31 bands (e.g., from 20 Hz to 20 kHz)
    band_edges = np.logspace(np.log10(200), np.log10(config['audio']['sample_rate'] // 2), NUM_BARS + 1)

    # Create a list to store the sum of magnitudes in each frequency band
    bands = []
    for i in range(NUM_BARS):
        # Frequency range for this band
        band_start = band_edges[i]
        band_end = band_edges[i + 1]

        # Find indices corresponding to the frequency range
        band_indices = np.where((freqs >= band_start) & (freqs < band_end))[0]

        # Sum the magnitudes of the frequencies in the current band
        band_magnitude = np.sum(magnitudes[band_indices])
        bands.append(band_magnitude)

    return np.array(bands)

# Function to draw the equalizer (bars)
def draw_equalizer(bands, barSurface):
    # Normalize the frequency data to fit the bar height
    max_height = (HEIGHT / 2) - 100
    normalized_bands = np.clip(bands / 100000, 0, 1)  # Normalize the bands
    #normalized_bands = bands
    max_width = WIDTH - 420

    BAR_WIDTH = max_width / NUM_BARS
    # Draw the bars for each frequency band

    for i in range(NUM_BARS):
        # Calculate the x position for each bar
        bar_x = i * BAR_WIDTH
        bar_height = int(normalized_bands[i] * max_height)

        # Bar color (color gradient from red to green to blue)
        color = (200 - int(bar_height * 100 / max_height), int(bar_height * 100 / max_height), 100)

        # Draw the rectangle (bar)

        pygame.draw.rect(barSurface, color, (bar_x, (HEIGHT/2) - bar_height, BAR_WIDTH, bar_height))


        #pygame.draw.rect(screen, color, (bar_x, HEIGHT - bar_height - 10, BAR_WIDTH, bar_height))

def scrollArtist():
    global artist_start_index


    if (len(last_artist_name) - artist_start_index < chunk_size):
        time.sleep(3)
        artist_start_index = 0
        time.sleep(3)
    else:
        artist_start_index += 1
        time.sleep(.2)

    scrollArtist()

def startArtistThreat():
    thread = threading.Thread(target=scrollArtist)
    thread.daemon = True
    thread.start()

def scrollSong():
    global track_start_index

    if (len(last_track_title) - track_start_index < chunk_size):
        time.sleep(3)
        track_start_index = 0
        time.sleep(3)
    else:
        track_start_index += 1
        time.sleep(.2)

    scrollSong()

def startSongThreat():
    thread = threading.Thread(target=scrollSong)
    thread.daemon = True
    thread.start()

def startApp():
    global running, artist_start_index, track_start_index
    clock = pygame.time.Clock()

    start_recognition_thread()
    startSongThreat()
    startArtistThreat()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        screen.fill((0, 0, 0))  # Fill the background with black

        # Event handling (to allow for graceful exit)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Get frequency data for 31 bands
        bands = get_frequency_bands()

        try:
            img = pygame.image.load(image_path)
            img = pygame.transform.scale(img, (400, 400))  # Resize image
            # Draw the image on the left
            screen.blit(img, (0, 100))
        except pygame.error:
            pass
        lastfm_img = pygame.image.load("lastfm.jpg")
        lastfm_img = pygame.transform.scale(lastfm_img, (50, 50))  # Resize image
        # Draw the image on the left
        screen.blit(lastfm_img, (10, 10))

        # Draw the text lines on the left
        screen.blit(font.render(config["lastfm"]["username"], True, (255, 255, 255)), (65, 20))


        barGraphSurface1 = pygame.surface.Surface((WIDTH - 400, HEIGHT/2))
        barGraphSurface1.fill((0, 0, 0))  # Fill the background with black

        # blit myNewSurface onto the main screen at the position (0, 0)
        # Draw the equalizer bars
        draw_equalizer(bands, barGraphSurface1)
        screen.blit(barGraphSurface1, (400, 0))


        barGraphSurface2 = pygame.transform.flip(barGraphSurface1, False, True)

        screen.blit(barGraphSurface2, (400, HEIGHT/2))

        # Draw the text lines on the left
        #screen.blit(font.render(last_track_title, True, (255, 255, 255)), (10, 500))


        last_artist_name_t = last_artist_name[artist_start_index:artist_start_index + chunk_size]

        text = font.render(last_artist_name_t, True, (255, 255, 255))
        text_rect = text.get_rect(center=(200, 20))
        screen.blit(text, (text_rect.x, 540))

        last_track_title_t = last_track_title[track_start_index:track_start_index + chunk_size]

        text = font.render(last_track_title_t, True, (255, 255, 255))
        text_rect = text.get_rect(center=(200, 20))
        screen.blit(text, (text_rect.x, 510))


        text = font.render(str(last_track_play_count) + ' Plays', True, (255, 255, 255))
        text_rect = text.get_rect(center=(200, 20))
        screen.blit(text, (text_rect.x, 70))

        # Update the display
        pygame.display.flip()
        # Limit the frame rate (FPS)
        clock.tick(60)

def stopApp():
    stream.stop_stream()
    stream.close()
    p.terminate()
    pygame.quit()

if __name__ == "__main__":
    startApp()
