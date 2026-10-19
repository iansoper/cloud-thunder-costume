# Thunder Cloud — hardware test. Checks each part on its own.
#
# Copy this file to CIRCUITPY (next to code.py), open the serial console,
# press Ctrl+C to stop code.py, then type:   import hardware_test
# Every step prints what you should see or hear. Press Ctrl+C to end the test.

import array
import math
import os
import time
import board
import neopixel
import audiobusio
import audiocore
from digitalio import DigitalInOut, Direction, Pull

NUM_ZONES = 6
LEDS_PER_ZONE = 10
BRIGHTNESS = 0.15      # low, so it also works from a laptop USB port

power = DigitalInOut(board.EXTERNAL_POWER)
power.direction = Direction.OUTPUT
power.value = True
print("External power ON (LED output + speaker amp)")

# ---- 1. LEDs: each zone lights in turn ----
pixels = neopixel.NeoPixel(board.EXTERNAL_NEOPIXELS, NUM_ZONES * LEDS_PER_ZONE,
                           brightness=BRIGHTNESS, auto_write=False)
COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
print("\n1. LEDs. Expect zone 1 red, 2 green, 3 blue, 4 yellow, 5 cyan, 6 magenta.")
for z in range(NUM_ZONES):
    pixels.fill((0, 0, 0))
    for i in range(z * LEDS_PER_ZONE, (z + 1) * LEDS_PER_ZONE):
        pixels[i] = COLORS[z]
    pixels.show()
    print("   zone", z + 1, "lit")
    time.sleep(1)
pixels.fill((40, 40, 40))
pixels.show()
print("   all 60 dim white. A segment that stays dark (and every one after it)")
print("   points to a bad joint at that segment's input.")
time.sleep(1.5)
pixels.fill((0, 0, 0))
pixels.show()

# ---- 2. Speaker: a 1-second test tone, no WAV file needed ----
print("\n2. Speaker. Expect a 1-second beep.")
audio = audiobusio.I2SOut(board.I2S_BIT_CLOCK, board.I2S_WORD_SELECT, board.I2S_DATA)
n = 50   # 22050 / 50 samples = 441 Hz
wave = array.array("h", [int(math.sin(2 * math.pi * i / n) * 8000) for i in range(n)])
tone = audiocore.RawSample(wave, sample_rate=22050)
audio.play(tone, loop=True)
time.sleep(1)
audio.stop()
print("   no beep? check the + and - screw terminals and the speaker wires.")

# ---- 3. Sound files ----
print("\n3. Sound files.")
for folder in ("/thunder", "/rain"):
    try:
        names = [f for f in os.listdir(folder) if f.lower().endswith(".wav") and not f.startswith(".")]
    except OSError:
        print("  ", folder, "folder not found")
        continue
    print("  ", folder, ":", len(names), "WAV file(s)")
    for name in names:
        path = folder + "/" + name
        try:
            w = audiocore.WaveFile(path)
            ok = w.channel_count == 1 and w.bits_per_sample == 16 and w.sample_rate == 22050
            print("     ", "OK  " if ok else "FIX ", name,
                  "(%d ch, %d-bit, %d Hz)" % (w.channel_count, w.bits_per_sample, w.sample_rate))
            w.deinit()
        except Exception as e:
            print("      FIX ", name, "-", e)

# ---- 4. Buttons and tap sensor (live) ----
print("\n4. Buttons and taps. Press each button and double-pat the board.")
print("   Red button lights zone 1, green button zone 2, a double pat zone 3.")
print("   Press Ctrl+C to finish.")


def button(pin):
    b = DigitalInOut(pin)
    b.direction = Direction.INPUT
    b.pull = Pull.UP
    return b


red = button(board.EXTERNAL_BUTTON)
green = button(board.A0)
lis = None
try:
    import adafruit_lis3dh
    lis = adafruit_lis3dh.LIS3DH_I2C(board.I2C(), int1=DigitalInOut(board.ACCELEROMETER_INTERRUPT))
    lis.range = adafruit_lis3dh.RANGE_8_G
    lis.set_tap(2, 20)
except Exception as e:
    print("   tap sensor not available:", e)

was_red = was_green = False
try:
    while True:
        r, g = not red.value, not green.value
        tap = bool(lis and lis.tapped)
        if r != was_red:
            print("   red button", "PRESSED" if r else "released")
        if g != was_green:
            print("   green button", "PRESSED" if g else "released")
        if tap:
            print("   double pat detected")
        pixels.fill((0, 0, 0))
        for zone, on in ((0, r), (1, g), (2, tap)):
            if on:
                for i in range(zone * LEDS_PER_ZONE, (zone + 1) * LEDS_PER_ZONE):
                    pixels[i] = (255, 255, 255)
        pixels.show()
        if tap:
            time.sleep(0.3)
        was_red, was_green = r, g
        time.sleep(0.02)
except KeyboardInterrupt:
    pixels.fill((0, 0, 0))
    pixels.show()
    print("\nTest finished. Press Ctrl+D to restart code.py.")
