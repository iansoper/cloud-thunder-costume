"""Build the Wokwi emulation copy of code.py.

The emulation keeps every line of the real light/button logic and only swaps:
  - Prop-Maker pin names -> Raspberry Pi Pico pins (same GPIO numbers where possible)
  - real audio -> stand-ins that "play" for a clip's length and print to the serial console
  - real WAV files -> 4 fake thunder clips + 1 rain loop with generated loudness patterns
  - tap sensor off (Wokwi can't simulate it); rain button on
Run:  python make_wokwi.py   (reads ../firmware/code.py, writes code.py next to this script)
"""
import pathlib
import re

here = pathlib.Path(__file__).parent
src = (here.parent / "firmware" / "code.py").read_text()


def swap(old, new, count=1):
    global src
    if src.count(old) < 1:
        raise SystemExit("pattern not found: " + old[:60])
    src = src.replace(old, new, count)


SHIMS = '''
# ======================= EMULATION SHIMS (Wokwi only) =======================
# Wokwi simulates the LEDs and buttons but not the speaker amp, so audio is
# replaced by stand-ins that "play" for the right length and print to the
# serial console. Everything below the shims is the real costume logic.


class _FakeWave:
    def __init__(self, path):
        self.path = path

    def deinit(self):
        pass


class _FakeVoice:
    def __init__(self, name):
        self.name = name
        self.level = 1.0
        self._until = 0
        self._loop = False
        self._path = None

    def play(self, wave, loop=False):
        self._path = wave.path
        self._loop = loop
        self._until = time.monotonic() + _FAKE_LENGTH.get(wave.path, 6)
        print("[sound] %s starts: %s%s" % (self.name, wave.path, " (looping)" if loop else ""))

    def stop(self):
        if self._loop or time.monotonic() < self._until:
            print("[sound] %s stops" % self.name)
        self._loop = False
        self._until = 0

    @property
    def playing(self):
        return self._loop or time.monotonic() < self._until


class _FakeMixer:
    def __init__(self, **kwargs):
        self.voice = [_FakeVoice("rain"), _FakeVoice("thunder")]


class _FakeI2S:
    def __init__(self, *args):
        pass

    def play(self, sample):
        pass


class _Namespace:
    pass


audiocore = _Namespace()
audiocore.WaveFile = _FakeWave
audiobusio = _Namespace()
audiobusio.I2SOut = _FakeI2S
audiomixer = _Namespace()
audiomixer.Mixer = _FakeMixer


def _fake_envelope(seconds, cracks):
    """A made-up loudness pattern: low rumble plus a few sharp cracks that fade."""
    n = int(seconds / 0.05)
    levels = []
    for i in range(n):
        t = i * 0.05
        lvl = 0.18 + 0.08 * math.sin(t * 2.3) + random.uniform(0, 0.05)
        for c in cracks:
            if c <= t < c + 1.5:
                lvl = max(lvl, math.exp(-(t - c) * 3.0))
        if t > seconds - 1.5:                  # fade out at the end
            lvl *= max(0.0, (seconds - t) / 1.5)
        levels.append(lvl)
    top = max(levels)
    return bytes(int(255 * v / top) for v in levels)


_FAKE_CLIPS = {                                # path: (seconds, crack times)
    "/thunder/thunder1.wav": (6, (0.3,)),
    "/thunder/thunder2.wav": (8, (0.2, 2.6)),
    "/thunder/thunder3.wav": (5, (1.2,)),
    "/thunder/thunder4.wav": (9, (0.4, 1.1, 4.5)),
}
_FAKE_LENGTH = {p: s for p, (s, c) in _FAKE_CLIPS.items()}
_FAKE_LENGTH["/rain/rain1.wav"] = 20
# ===================== END EMULATION SHIMS ==================================
'''

# 1. audio modules -> shims (inserted after the digitalio import)
swap("import audiocore\nimport audiobusio\nimport audiomixer\n", "")
swap("from digitalio import DigitalInOut, Direction, Pull\n",
     "from digitalio import DigitalInOut, Direction, Pull\n" + SHIMS)

# 2. settings that differ in the emulator
swap("USE_TAP = True ", "USE_TAP = False")
swap("USE_RAIN_BUTTON = False", "USE_RAIN_BUTTON = True ")
swap("BRIGHTNESS = 0.35", "BRIGHTNESS = 0.8 ")

# 3. pins: Prop-Maker -> Pico (LED data GP21 and thunder button GP19 match the
#    Prop-Maker's GPIO numbers; rain button stays on A0 = GP26)
swap("""external_power = DigitalInOut(board.EXTERNAL_POWER)
external_power.direction = Direction.OUTPUT
external_power.value = True
""", "# (Pico has no external-power switch to turn on)\n")
swap("board.EXTERNAL_NEOPIXELS", "board.GP21")
swap("board.EXTERNAL_BUTTON", "board.GP19")
swap("audiobusio.I2SOut(board.I2S_BIT_CLOCK, board.I2S_WORD_SELECT, board.I2S_DATA)",
     "audiobusio.I2SOut()")

# 4. fake clip lists instead of reading the drive
swap('sounds = list_wavs("/thunder")', "sounds = sorted(_FAKE_CLIPS)")
swap('rain_sounds = list_wavs("/rain") if USE_RAIN_BUTTON else []',
     'rain_sounds = ["/rain/rain1.wav"] if USE_RAIN_BUTTON else []')

# 5. generated loudness patterns instead of measuring WAV files
src = re.sub(r"\nenvelopes = \{\}\nif SOUND_REACTIVE and sounds:.*?\n(?=\n\ndef make_button)",
             "\nenvelopes = {}\nif SOUND_REACTIVE:\n"
             "    for _p, (_s, _c) in _FAKE_CLIPS.items():\n"
             "        envelopes[_p] = _fake_envelope(_s, _c)\n",
             src, count=1, flags=re.S)
if "_fake_envelope(_s, _c)" not in src:
    raise SystemExit("envelope block not replaced")

# 6. header
swap("# Thunder Cloud costume — Adafruit RP2040 Prop-Maker Feather",
     "# Thunder Cloud costume — WOKWI EMULATION (Raspberry Pi Pico), not for the real board\n"
     "# Real board: use the regular code.py. This copy fakes the audio and swaps pins.\n#\n"
     "# Original header:\n# Thunder Cloud costume — Adafruit RP2040 Prop-Maker Feather")

(here / "code.py").write_text(src)
print("wrote", here / "code.py")
