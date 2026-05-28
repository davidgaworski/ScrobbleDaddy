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
NUM_BARS = 32

last_track_title = ""
last_artist_name = ""
last_track_play_count = 0
last_cover_art_url = ""

# Set up the display
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("ScrobbleDaddy")

# Color palette (matching ScrobbleDaddy branding)
BG_COLOR = (12, 12, 20)
TEXT_COLOR = (240, 240, 245)
TEXT_DIM = (160, 160, 175)
BORDER_COLOR = (80, 40, 140)

# Layout constants
LEFT_PANEL_W = 400
ART_SIZE = 350
ART_X = (LEFT_PANEL_W - ART_SIZE) // 2
ART_Y = 80
BAR_GAP = 3

# Fonts
font_title = pygame.font.SysFont("Arial", 28, bold=True)
font_artist = pygame.font.SysFont("Arial", 22)
font_small = pygame.font.SysFont("Arial", 16)

# Image cache (avoid reloading from disk every frame)
cached_album_art = None
cached_album_art_path = None
cached_lastfm_img = None

# Pre-allocate surfaces (reuse each frame instead of creating new ones)
bar_surface = pygame.surface.Surface((WIDTH - LEFT_PANEL_W, HEIGHT // 2))

# Equalizer smoothing state
prev_bands = None

# Vinyl record state
cached_vinyl = None
vinyl_angle = 0
VINYL_SIZE = 120
VINYL_SPEED = 2.0  # degrees per frame
cached_rotated_vinyl = None
vinyl_frame_counter = 0

chunk_size = 30
track_start_index = 0
artist_start_index = 0

# Pre-compute bar colors (purple → magenta → hot pink gradient)
bar_colors = []
for _i in range(NUM_BARS):
    t = _i / max(NUM_BARS - 1, 1)
    if t < 0.5:
        _t2 = t * 2
        r = int(100 + (180 - 100) * _t2)
        g = int(40 + (40 - 40) * _t2)
        b = int(200 + (180 - 200) * _t2)
    else:
        _t2 = (t - 0.5) * 2
        r = int(180 + (255 - 180) * _t2)
        g = int(40 + (60 - 40) * _t2)
        b = int(180 + (140 - 180) * _t2)
    bar_colors.append((r, g, b))

# Set environment variable for ALSA (must be before pyaudio init)
os.environ['PA_ALSA_PLUGHW'] = '1'

p = pyaudio.PyAudio()

# Find a working input device
def open_audio_stream():
    """Try configured device, then fall back to default."""
    device_index = config['audio'].get('device_index', None)
    rate = config['audio']['sample_rate']
    chunk = config['audio']['chunk_size']

    # Try configured device first
    if device_index is not None:
        try:
            s = p.open(format=pyaudio.paInt16, channels=1, rate=rate,
                       input=True, frames_per_buffer=chunk,
                       input_device_index=device_index)
            print(f"Audio stream opened on device {device_index}")
            return s
        except Exception as e:
            print(f"Device {device_index} failed: {e} — trying default...")

    # Fall back to default device
    try:
        s = p.open(format=pyaudio.paInt16, channels=1, rate=rate,
                   input=True, frames_per_buffer=chunk)
        print("Audio stream opened on default device")
        return s
    except Exception as e:
        print(f"Default device failed: {e} — trying all devices...")

    # Try every input device
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            try:
                s = p.open(format=pyaudio.paInt16, channels=1, rate=rate,
                           input=True, frames_per_buffer=chunk,
                           input_device_index=i)
                print(f"Audio stream opened on device {i}: {info['name']}")
                return s
            except Exception:
                continue

    print("ERROR: No working audio input device found!")
    return None

stream = open_audio_stream()

# Initialize Last.fm network (optional — runs without it)
network = None
lastfm_enabled = False

if (config['lastfm']['api_key'] and config['lastfm']['api_secret']
        and config['lastfm']['username'] and config['lastfm']['password']):
    try:
        network = pylast.LastFMNetwork(
            api_key=config['lastfm']['api_key'],
            api_secret=config['lastfm']['api_secret'],
            username=config['lastfm']['username'],
            password_hash=pylast.md5(config['lastfm']['password']),
        )
        lastfm_enabled = True
        print(f"Last.fm connected as: {config['lastfm']['username']}")
    except Exception as e:
        print(f"Last.fm connection failed: {e} — running without scrobbling")
else:
    print("Last.fm credentials not configured — running without scrobbling")

duration = 10  # seconds

isRecording = False

def record_audio():
    global isRecording
    samplerate = 44100  # Hertz
    filename = 'output.wav'

    isRecording = True
    try:
        print(f"Recording {config['audio']['record_seconds']}s...")
        mydata = sd.rec(int(samplerate * config['audio']['record_seconds']), samplerate=44100,
                        channels=1, blocking=True)

        sf.write(filename, mydata, samplerate)
        print(f"Recording saved to {filename}")
        isRecording = False
        return filename
    except Exception as e:
        print(f"Recording error: {e}")
        isRecording = False
        return None

async def recognize_song(wav_file):
    shazam = Shazam()

    try:
        return await shazam.recognize(wav_file)
    except Exception as e:
        print(f"Error recognizing song: {e}")
    return None

def song_play_count(result):
    global last_track_play_count

    if not lastfm_enabled:
        return

    track_title = result['track']['title']
    artist_name = result['track']['subtitle']

    track = pylast.Track(
        artist=artist_name, title=track_title, network=network, username=config["lastfm"]["username"]
    )

    try:
        last_track_play_count = track.get_userplaycount()
    except Exception as e:
        print(f"Error getting play count: {e}")
    print(last_track_play_count, "playcount")

def scrobbleMeDaddy(result):
    if not lastfm_enabled:
        title = result['track']['title']
        artist = result['track']['subtitle']
        print(f"Detected: {artist} - {title} (Last.fm not configured, skipping scrobble)")
        return

    # Scrobble a track
    title = result['track']['title']
    artist = result['track']['subtitle']
    try:
        album = result['track']['sections'][0]['metadata'][0]['text']
    except (KeyError, IndexError):
        album = ''

    unix_timestamp = int(time.mktime(datetime.datetime.now().timetuple()))
    print(f"Scrobbling: {artist} - {title} (Timestamp: {unix_timestamp})")

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
                invalidate_album_cache()

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
            print("Song recognized successfully")
            update_gui(result)
    else:
        print("Failed to record audio")

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
    global prev_bands

    max_height = (HEIGHT // 2) - 40
    max_width = WIDTH - LEFT_PANEL_W - 20
    bar_width = max(2, (max_width / NUM_BARS) - BAR_GAP)

    # Smooth animation — blend with previous frame
    if prev_bands is not None and len(prev_bands) == len(bands):
        bands = 0.35 * bands + 0.65 * prev_bands
    prev_bands = bands.copy()

    # Dynamic normalization
    peak = np.max(bands)
    if peak > 0:
        normalized_bands = np.clip(bands / peak, 0, 1)
    else:
        normalized_bands = np.zeros(NUM_BARS)

    for i in range(NUM_BARS):
        bar_x = i * (bar_width + BAR_GAP)
        bar_height = max(2, int(normalized_bands[i] * max_height))

        # Brighten taller bars
        brightness = 0.55 + 0.45 * (bar_height / max_height)
        r = min(255, int(bar_colors[i][0] * brightness))
        g = min(255, int(bar_colors[i][1] * brightness))
        b = min(255, int(bar_colors[i][2] * brightness))

        pygame.draw.rect(barSurface, (r, g, b),
                         (bar_x, (HEIGHT // 2) - bar_height, bar_width, bar_height))

def scrollArtist():
    global artist_start_index

    while True:
        if (len(last_artist_name) - artist_start_index < chunk_size):
            time.sleep(3)
            artist_start_index = 0
            time.sleep(3)
        else:
            artist_start_index += 1
            time.sleep(.2)

def startArtistThread():
    thread = threading.Thread(target=scrollArtist)
    thread.daemon = True
    thread.start()

def scrollSong():
    global track_start_index

    while True:
        if (len(last_track_title) - track_start_index < chunk_size):
            time.sleep(3)
            track_start_index = 0
            time.sleep(3)
        else:
            track_start_index += 1
            time.sleep(.2)

def startSongThread():
    thread = threading.Thread(target=scrollSong)
    thread.daemon = True
    thread.start()

def load_cached_image(path, size, cache_attr):
    """Load and cache an image — only reloads from disk when the file changes."""
    global cached_album_art, cached_album_art_path, cached_lastfm_img
    if cache_attr == 'album':
        if cached_album_art is not None and cached_album_art_path == path:
            return cached_album_art
        try:
            img = pygame.image.load(path).convert()
            img = pygame.transform.scale(img, size)
            cached_album_art = img
            cached_album_art_path = path
            return img
        except (pygame.error, FileNotFoundError):
            return None
    elif cache_attr == 'lastfm':
        if cached_lastfm_img is not None:
            return cached_lastfm_img
        try:
            img = pygame.image.load(path).convert()
            img = pygame.transform.scale(img, size)
            cached_lastfm_img = img
            return img
        except (pygame.error, FileNotFoundError):
            return None

def invalidate_album_cache():
    """Call this when a new album art is downloaded."""
    global cached_album_art, cached_album_art_path, cached_vinyl
    cached_album_art = None
    cached_album_art_path = None
    cached_vinyl = None

def create_vinyl(size, label_img=None):
    """Create a vinyl record surface with optional album art as the center label."""
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    center = size // 2
    radius = center - 2

    # Vinyl disc
    pygame.draw.circle(surface, (30, 30, 35), (center, center), radius)

    # Outer rim
    pygame.draw.circle(surface, (55, 55, 60), (center, center), radius, 2)

    # Grooves (concentric rings)
    for r in range(radius - 8, size // 4, -5):
        pygame.draw.circle(surface, (40, 40, 45), (center, center), r, 1)

    # Center label
    label_radius = size // 5
    label_size = label_radius * 2

    if label_img:
        try:
            scaled = pygame.transform.scale(label_img, (label_size, label_size))
            temp = pygame.Surface((label_size, label_size), pygame.SRCALPHA)
            temp.blit(scaled, (0, 0))
            # Circular mask
            mask = pygame.Surface((label_size, label_size), pygame.SRCALPHA)
            pygame.draw.circle(mask, (255, 255, 255, 255),
                               (label_radius, label_radius), label_radius)
            temp.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            surface.blit(temp, (center - label_radius, center - label_radius))
        except Exception:
            pygame.draw.circle(surface, (80, 40, 140), (center, center), label_radius)
    else:
        pygame.draw.circle(surface, (80, 40, 140), (center, center), label_radius)

    # Spindle hole
    pygame.draw.circle(surface, (15, 15, 20), (center, center), 3)
    pygame.draw.circle(surface, (60, 60, 65), (center, center), 3, 1)

    return surface

def startApp():
    global running, artist_start_index, track_start_index, vinyl_angle, cached_vinyl, cached_rotated_vinyl, vinyl_frame_counter
    clock = pygame.time.Clock()

    start_recognition_thread()
    startSongThread()
    startArtistThread()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        screen.fill(BG_COLOR)

        # --- Get audio data ---
        bands = get_frequency_bands()

        # --- Left Panel: Album Art ---
        art_img = load_cached_image("image.jpg", (ART_SIZE, ART_SIZE), 'album')
        if art_img:
            # Draw border around album art
            pygame.draw.rect(screen, BORDER_COLOR,
                             (ART_X - 3, ART_Y - 3, ART_SIZE + 6, ART_SIZE + 6),
                             border_radius=4)
            screen.blit(art_img, (ART_X, ART_Y))
        else:
            # Placeholder when no song detected yet
            pygame.draw.rect(screen, (25, 25, 40),
                             (ART_X, ART_Y, ART_SIZE, ART_SIZE),
                             border_radius=4)
            ph = font_small.render("Listening...", True, (80, 80, 110))
            ph_rect = ph.get_rect(center=(ART_X + ART_SIZE // 2, ART_Y + ART_SIZE // 2))
            screen.blit(ph, ph_rect)

        # --- Left Panel: Song Info ---
        info_y = ART_Y + ART_SIZE + 20

        title_text = last_track_title[track_start_index:track_start_index + chunk_size]
        if title_text:
            surf = font_title.render(title_text, True, TEXT_COLOR)
            rect = surf.get_rect(centerx=LEFT_PANEL_W // 2, y=info_y)
            screen.blit(surf, rect)

        artist_text = last_artist_name[artist_start_index:artist_start_index + chunk_size]
        if artist_text:
            surf = font_artist.render(artist_text, True, TEXT_DIM)
            rect = surf.get_rect(centerx=LEFT_PANEL_W // 2, y=info_y + 35)
            screen.blit(surf, rect)

        # --- Left Panel: Last.fm Info ---
        if lastfm_enabled:
            lfm_img = load_cached_image("lastfm.jpg", (28, 28), 'lastfm')
            if lfm_img:
                screen.blit(lfm_img, (12, 12))
            screen.blit(font_small.render(config["lastfm"]["username"], True, TEXT_DIM), (45, 15))

            plays = font_small.render(str(last_track_play_count) + ' plays', True, TEXT_DIM)
            plays_rect = plays.get_rect(centerx=LEFT_PANEL_W // 2, y=info_y + 68)
            screen.blit(plays, plays_rect)

        # --- Divider ---
        pygame.draw.line(screen, (40, 20, 70),
                         (LEFT_PANEL_W, 0), (LEFT_PANEL_W, HEIGHT), 1)

        # --- Right Panel: Visualizer ---
        bar_surface.fill(BG_COLOR)
        draw_equalizer(bands, bar_surface)
        screen.blit(bar_surface, (LEFT_PANEL_W, 0))

        # --- Spinning Vinyl Record (rotate every 3rd frame) ---
        vinyl_angle = (vinyl_angle + VINYL_SPEED) % 360
        vinyl_frame_counter += 1

        if cached_vinyl is None:
            cached_vinyl = create_vinyl(VINYL_SIZE, art_img)

        if cached_rotated_vinyl is None or vinyl_frame_counter % 3 == 0:
            cached_rotated_vinyl = pygame.transform.rotate(cached_vinyl, vinyl_angle)

        rot_rect = cached_rotated_vinyl.get_rect(
            center=(WIDTH - VINYL_SIZE // 2 - 20, HEIGHT - VINYL_SIZE // 2 - 15))
        screen.blit(cached_rotated_vinyl, rot_rect)

        # --- Flip ---
        pygame.display.flip()
        clock.tick(30)

def stopApp():
    stream.stop_stream()
    stream.close()
    p.terminate()
    pygame.quit()

if __name__ == "__main__":
    startApp()
