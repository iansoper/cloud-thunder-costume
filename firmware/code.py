# Thunder Cloud costume — Adafruit RP2040 Prop-Maker Feather (CircuitPython 10.x)
#
# Wiring (screw terminal block):
#   Neo -> LED strip DIN     5V -> strip 5V     G -> strip GND (+ button)
#   Btn -> thunder button    + / - -> speaker (never connect either speaker wire to G)
#   Optional rain button: A0 pad and a GND pad on the board's edge (USE_RAIN_BUTTON = True)
# Power: USB-C power bank into the board's USB-C port.
#
# Files on the CIRCUITPY drive:
#   code.py            (this file)
#   safemode.py        (auto-restarts the board after a power dip)
#   lib/neopixel.mpy
#   lib/adafruit_lis3dh.mpy
#   lib/adafruit_bus_device/   (folder)
#   thunder/*.wav      thunder clips (16-bit, mono, 22050 Hz — every file must match exactly)
#   rain/*.wav         optional rain loops, same format

import os
import math
import time
import random
import board
import audiocore
import audiobusio
import audiomixer
import neopixel
from digitalio import DigitalInOut, Direction, Pull

# ---------------- SETTINGS — tweak these ----------------
USE_BUTTON = True          # trigger strikes with the button on Btn/G
USE_TAP = True             # trigger strikes by patting the cloud
TAP_MODE = 2               # 2 = double pat (fewer false triggers while dancing), 1 = single
TAP_THRESHOLD = 20         # lower = more sensitive (try 10–30)

AMBIENT = "off"            # automatic strikes: "off" = thunder only on a press (or pat),
                           # "raining" = also random strikes while rain is on,
                           # "always" = random strikes all night
AMBIENT_MIN_S = 25         # shortest gap between random strikes (seconds)
AMBIENT_MAX_S = 90         # longest gap

NUM_ZONES = 6              # segments you cut the strip into
LEDS_PER_ZONE = 10         # LEDs in each segment
BRIGHTNESS = 0.35          # overall cap, 0.0–1.0 (keep <= 0.4 on a power bank;
                           # use ~0.15 when testing from a laptop USB port)
VOLUME = 1.0               # thunder volume, 0.0–1.0
THUNDER_DELAY = (0.05, 0.6)  # seconds between the flash and the thunder (min, max)
MAX_THUNDER_S = 20         # longest a thunder clip may play before the next strike can start

IDLE_COLOR = (6, 8, 22)    # dim storm-blue glow between strikes (raise it if the
                           # power bank shuts off when idle)
FLASH_COLOR = (255, 255, 255)
DIM_FLASH = (90, 100, 140)

KEEPALIVE_S = 12           # faint distant flicker this often (storm atmosphere)

READY_FLASH = True         # flash blue once the sounds are loaded and the cloud is ready
READY_COLOR = (0, 70, 255)
READY_FLASHES = 3

SOUND_REACTIVE = True      # lights follow the loudness of the thunder clip
RUMBLE_COLOR = (130, 140, 190)  # cloud color at the clip's loudest moment
PEAK_LEVEL = 0.6           # loudness (0–1) that counts as a crack of thunder...
PEAK_JUMP = 0.2            # ...when it rises at least this much in one step -> a flash
SYNC_OFFSET_S = 0.0        # if the lights run ahead of the sound, raise to e.g. 0.05

# Optional rain button (second button, wired to the A0 pad and a GND pad)
USE_RAIN_BUTTON = False    # True once the rain button is wired; press = rain on/off
RAIN_PIN = board.A0
RAIN_VOLUME = 0.6          # rain loudness, 0.0–1.0
RAIN_DUCK = 0.3            # rain drops to this share of RAIN_VOLUME during thunder
RAIN_DROP_COLOR = (25, 35, 80)  # the faint flickers that drift through the cloud while raining
RAIN_DROPS = 3             # how many LEDs flicker at a time while raining
# --------------------------------------------------------

NUM_PIXELS = NUM_ZONES * LEDS_PER_ZONE
SAMPLE_RATE = 22050

# Power on the LED output and speaker amp (off by default on this board)
external_power = DigitalInOut(board.EXTERNAL_POWER)
external_power.direction = Direction.OUTPUT
external_power.value = True

pixels = neopixel.NeoPixel(board.EXTERNAL_NEOPIXELS, NUM_PIXELS,
                           brightness=BRIGHTNESS, auto_write=False)

# Audio goes through a two-channel mixer: voice 0 = rain loop, voice 1 = thunder
RAIN, THUNDER = 0, 1
audio = audiobusio.I2SOut(board.I2S_BIT_CLOCK, board.I2S_WORD_SELECT, board.I2S_DATA)
mixer = audiomixer.Mixer(voice_count=2, sample_rate=SAMPLE_RATE, channel_count=1,
                         bits_per_sample=16, samples_signed=True, buffer_size=2048)
audio.play(mixer)
mixer.voice[THUNDER].level = VOLUME
mixer.voice[RAIN].level = RAIN_VOLUME
current_wave = None
rain_wave = None
raining = False


def list_wavs(folder):
    """WAV files in folder that are in the right format (others are skipped)."""
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for name in names:
        if not name.lower().endswith(".wav") or name.startswith("."):
            continue
        path = folder + "/" + name
        try:
            with open(path, "rb") as f:
                ok = wav_data_size(f) and wav_sample_rate(path) == SAMPLE_RATE
        except OSError:
            ok = False
        if ok:
            found.append(path)
        else:
            print("Skipping", path, "- needs 16-bit mono WAV at", SAMPLE_RATE, "Hz")
    return found

# ---- Loudness envelopes: measured once at power-up so the lights can follow the sound ----
ENV_WINDOW_S = 0.05        # one loudness value per 50 ms of audio


def wav_data_size(f):
    """Move f to the start of the audio data; return its size in bytes,
    or None if the file isn't 16-bit mono WAV."""
    head = f.read(12)
    if len(head) < 12 or head[0:4] != b"RIFF" or head[8:12] != b"WAVE":
        return None
    fmt_ok = False
    while True:
        chunk = f.read(8)
        if len(chunk) < 8:
            return None
        cid = chunk[0:4]
        size = int.from_bytes(chunk[4:8], "little")
        if cid == b"fmt ":
            fmt = f.read(size + (size & 1))
            channels = int.from_bytes(fmt[2:4], "little")
            bits = int.from_bytes(fmt[14:16], "little")
            fmt_ok = channels == 1 and bits == 16
        elif cid == b"data":
            return size if fmt_ok else None
        else:
            f.seek(size + (size & 1), 1)


def wav_sample_rate(path):
    """Sample rate from the WAV's fmt chunk (0 if unreadable)."""
    with open(path, "rb") as f:
        if f.read(12)[8:12] != b"WAVE":
            return 0
        while True:
            chunk = f.read(8)
            if len(chunk) < 8:
                return 0
            size = int.from_bytes(chunk[4:8], "little")
            if chunk[0:4] == b"fmt ":
                fmt = f.read(size)
                return int.from_bytes(fmt[4:8], "little")
            f.seek(size + (size & 1), 1)


sounds = list_wavs("/thunder")
rain_sounds = list_wavs("/rain") if USE_RAIN_BUTTON else []
print("Thunder files:", sounds)
if USE_RAIN_BUTTON:
    print("Rain files:", rain_sounds)


def compute_envelope(path, np):
    """Loudness of each 50 ms slice of a clip, scaled 0–255 (loudest = 255)."""
    win = int(SAMPLE_RATE * ENV_WINDOW_S)
    buf = bytearray(win * 2)
    levels = []
    with open(path, "rb") as f:
        remaining = wav_data_size(f)
        if not remaining:
            return None
        while remaining >= 2:
            want = min(len(buf), remaining - (remaining & 1))
            n = f.readinto(memoryview(buf)[:want])
            if not n or n < 2:
                break
            remaining -= n
            samples = np.array(np.frombuffer(buf, dtype=np.int16, count=n // 2),
                               dtype=np.float)
            levels.append(math.sqrt(np.mean(samples * samples)))
    if not levels:
        return None
    loudest = max(levels) or 1
    return bytes(int(255 * v / loudest) for v in levels)


envelopes = {}
if SOUND_REACTIVE and sounds:
    try:
        from ulab import numpy as ulab_np
        pixels.fill((0, 0, 12))            # dim blue while measuring
        pixels.show()
        t0 = time.monotonic()
        for path in sounds:
            try:
                env = compute_envelope(path, ulab_np)
                if env:
                    envelopes[path] = env
            except Exception as e:
                print("Couldn't measure", path, e)
        print("Measured", len(envelopes), "clips in", round(time.monotonic() - t0, 1), "s")
    except ImportError:
        print("ulab not available; using random rumble instead")


def make_button(pin):
    b = DigitalInOut(pin)
    b.direction = Direction.INPUT
    b.pull = Pull.UP               # pressed = connected to ground = reads False
    return b


button = make_button(board.EXTERNAL_BUTTON) if USE_BUTTON else None
rain_button = make_button(RAIN_PIN) if USE_RAIN_BUTTON else None

lis3dh = None
if USE_TAP:
    try:
        import adafruit_lis3dh
        i2c = board.I2C()
        int1 = DigitalInOut(board.ACCELEROMETER_INTERRUPT)
        lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, int1=int1)
        lis3dh.range = adafruit_lis3dh.RANGE_8_G
        lis3dh.set_tap(TAP_MODE, TAP_THRESHOLD)
    except Exception as e:  # keep running even if the sensor fails
        print("Tap sensor unavailable:", e)
        lis3dh = None


def zone_range(z):
    start = z * LEDS_PER_ZONE
    return range(start, start + LEDS_PER_ZONE)


def idle():
    pixels.fill(IDLE_COLOR)
    pixels.show()


def light_zones(zones, color):
    pixels.fill(IDLE_COLOR)
    for z in zones:
        for i in zone_range(z):
            pixels[i] = color
    pixels.show()


def flicker(zones, count, color=FLASH_COLOR):
    """Fast stutter, like the leader stroke before a big flash."""
    for _ in range(count):
        light_zones(zones, color)
        time.sleep(random.uniform(0.02, 0.06))
        idle()
        time.sleep(random.uniform(0.03, 0.12))


def play_thunder():
    """Play a random clip, closing the previous one so files never pile up."""
    global current_wave
    if not sounds:
        return None
    try:
        mixer.voice[THUNDER].stop()
        if current_wave is not None:
            current_wave.deinit()
            current_wave = None
        path = random.choice(sounds)
        current_wave = audiocore.WaveFile(path)
        mixer.voice[THUNDER].play(current_wave)
        return path
    except Exception as e:  # e.g. a WAV in the wrong format
        print("Audio error:", e)
        return None


def thunder_playing():
    return mixer.voice[THUNDER].playing


def start_rain():
    """Loop a random rain clip on its own mixer channel."""
    global rain_wave, raining
    if not rain_sounds:
        return
    try:
        stop_rain()
        rain_wave = audiocore.WaveFile(random.choice(rain_sounds))
        mixer.voice[RAIN].level = RAIN_VOLUME
        mixer.voice[RAIN].play(rain_wave, loop=True)
        raining = True
    except Exception as e:
        print("Rain audio error:", e)


def stop_rain():
    global rain_wave, raining
    mixer.voice[RAIN].stop()
    if rain_wave is not None:
        rain_wave.deinit()
        rain_wave = None
    raining = False


def rain_frame():
    """Dim glow with a few faint flickers drifting through random spots."""
    pixels.fill(IDLE_COLOR)
    for _ in range(RAIN_DROPS):
        pixels[random.randrange(NUM_PIXELS)] = RAIN_DROP_COLOR
    pixels.show()


def rest():
    """The look between strikes: plain glow, or the rain shimmer while raining."""
    if raining:
        rain_frame()
    else:
        idle()


def clear_taps():
    """Discard any pat latched while a strike was running."""
    if lis3dh is not None:
        try:
            lis3dh.tapped
        except Exception:
            pass


def random_zones(n):
    """n different zones, chosen at random."""
    pool = list(range(NUM_ZONES))
    picked = []
    for _ in range(min(n, NUM_ZONES)):
        picked.append(pool.pop(random.randrange(len(pool))))
    return picked


def strike():
    """One lightning strike in randomly chosen zones, then thunder.

    Each strike picks a random style so no two look the same:
      single - one zone flashes hard
      jump   - the bolt hops between 2-4 random zones
      burst  - 2-3 random zones flash together
      sheet  - the whole cloud lights, brightest in one random zone
    """
    style = random.choice(("single", "single", "jump", "jump", "burst", "sheet"))
    zones = random_zones(1)

    flicker(zones, random.randint(1, 3), DIM_FLASH)      # build-up

    if style == "single":
        light_zones(zones, FLASH_COLOR)
        time.sleep(random.uniform(0.06, 0.14))
    elif style == "jump":
        zones = random_zones(random.randint(2, 4))
        for z in zones:
            light_zones([z], FLASH_COLOR)
            time.sleep(random.uniform(0.04, 0.09))
    elif style == "burst":
        zones = random_zones(random.randint(2, 3))
        light_zones(zones, FLASH_COLOR)
        time.sleep(random.uniform(0.08, 0.16))
    else:  # sheet
        pixels.fill(DIM_FLASH)
        for i in zone_range(zones[0]):
            pixels[i] = FLASH_COLOR
        pixels.show()
        time.sleep(random.uniform(0.1, 0.2))

    idle()
    time.sleep(random.uniform(0.05, 0.15))
    flicker(zones, random.randint(1, 3))                 # after-flashes

    time.sleep(random.uniform(*THUNDER_DELAY))
    if raining:
        mixer.voice[RAIN].level = RAIN_VOLUME * RAIN_DUCK   # let the thunder cut through
    path = play_thunder()
    env = envelopes.get(path) if path else None

    if env:
        follow_sound(env, zones)
    else:
        random_rumble()
    if raining:
        mixer.voice[RAIN].level = RAIN_VOLUME
    rest()
    clear_taps()   # pats (or speaker rumble) during the strike don't queue another


def blend(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def follow_sound(env, focus):
    """Cloud brightness tracks the clip's loudness; sharp cracks flash.
    The zones the bolt hit (focus) glow strongest, the rest at about half."""
    start = time.monotonic() + SYNC_OFFSET_S
    t_end = start + MAX_THUNDER_S
    prev = 0.0
    while thunder_playing() and time.monotonic() < t_end:
        i = int((time.monotonic() - start) / ENV_WINDOW_S)
        if i >= len(env):
            break
        level = env[i] / 255 if i >= 0 else 0.0
        if level >= PEAK_LEVEL and level - prev >= PEAK_JUMP:
            light_zones(random_zones(random.randint(1, 2)), FLASH_COLOR)   # crack
            time.sleep(random.uniform(0.03, 0.06))
        shaped = level ** 1.5            # keeps quiet rumble dim, loud parts bright
        outer = blend(IDLE_COLOR, RUMBLE_COLOR, shaped * 0.5)
        inner = blend(IDLE_COLOR, RUMBLE_COLOR, shaped)
        pixels.fill(outer)
        for z in focus:
            for p in zone_range(z):
                pixels[p] = inner
        pixels.show()
        prev = level
        time.sleep(0.02)


def random_rumble():
    """Fallback when a clip couldn't be measured: faint random flickers."""
    t_end = time.monotonic() + MAX_THUNDER_S
    while thunder_playing() and time.monotonic() < t_end:
        if random.random() < 0.15:
            z = random.randrange(NUM_ZONES)
            light_zones([z], DIM_FLASH)
            time.sleep(random.uniform(0.02, 0.05))
            idle()
        time.sleep(0.08)


def pressed(b):
    """True once per press of button b (debounced; waits for release)."""
    if b is None or b.value:
        return False
    time.sleep(0.02)                      # debounce
    if b.value:
        return False
    release_by = time.monotonic() + 2     # don't hang if the button sticks
    while not b.value and time.monotonic() < release_by:
        time.sleep(0.01)
    return True


def ambient_allowed():
    if AMBIENT == "always":
        return True
    if AMBIENT == "raining":
        return raining or not USE_RAIN_BUTTON
    return False


def tapped():
    if lis3dh is None:
        return False
    try:
        return bool(lis3dh.tapped)
    except Exception:
        return False


def next_ambient():
    return time.monotonic() + random.uniform(AMBIENT_MIN_S, AMBIENT_MAX_S)


def blink(color):
    for _ in range(3):
        pixels.fill(color)
        pixels.show()
        time.sleep(0.25)
        pixels.fill((0, 0, 0))
        pixels.show()
        time.sleep(0.25)


def ready_flash():
    """Blue flashes: sounds are loaded and the cloud is ready for button presses."""
    if not READY_FLASH:
        return
    for _ in range(READY_FLASHES):
        pixels.fill(READY_COLOR)
        pixels.show()
        time.sleep(0.15)
        idle()
        time.sleep(0.15)


def boot_check():
    """Red blinks = no thunder files found; amber blinks = rain button on but no rain files."""
    if not sounds:
        blink((60, 0, 0))
    if USE_RAIN_BUTTON and not rain_sounds:
        blink((60, 30, 0))


# ---------------- main loop ----------------
boot_check()
ready_flash()
idle()
clear_taps()
ambient_at = next_ambient()
keepalive_at = time.monotonic() + KEEPALIVE_S
rain_frame_at = 0

while True:
    now = time.monotonic()

    if pressed(button) or tapped():
        strike()
        ambient_at = next_ambient()
    elif pressed(rain_button):
        if raining:
            stop_rain()
        else:
            start_rain()
        rest()
        ambient_at = next_ambient()
    elif ambient_allowed() and now >= ambient_at:
        strike()
        ambient_at = next_ambient()
    elif raining and now >= rain_frame_at:
        rain_frame()
        rain_frame_at = now + 0.07
    elif not raining and now >= keepalive_at:
        light_zones([random.randrange(NUM_ZONES)], DIM_FLASH)
        time.sleep(0.04)
        idle()
        keepalive_at = now + KEEPALIVE_S

    time.sleep(0.01)
