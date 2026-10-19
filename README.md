# Cloud Thunder Costume

A wearable storm cloud: fiberfill with LEDs inside that flash like lightning, with thunder from a hidden speaker. A red button sets off a strike, an optional green button turns rain on and off, and the lights follow the loudness of each thunder clip.

Built on the [Adafruit RP2040 Prop-Maker Feather](https://www.adafruit.com/product/5768), a WS2812B LED strip cut into six zones, a 3 W speaker and a USB-C power bank, running CircuitPython.

![Wiring overview](docs/images/wiring-overview.png)

## What's here

| Path | What it is |
| --- | --- |
| [`docs/build-guide.md`](docs/build-guide.md) | Parts, wiring diagrams, soldering, software setup, testing and troubleshooting |
| [`docs/parts-and-costs.xlsx`](docs/parts-and-costs.xlsx) | Price estimates and purchase links for two builds (ESP32 and Prop-Maker) |
| [`firmware/code.py`](firmware/code.py) | The costume code; copy to the board's `CIRCUITPY` drive |
| [`firmware/safemode.py`](firmware/safemode.py) | Restarts the board after a power dip instead of staying dark |
| [`preview/storm-preview.html`](preview/storm-preview.html) | Browser preview: press the buttons, load your own WAVs, tune settings |
| [`audio/`](audio) | Thunder clips and rain loops, laid out like the board's drive, with creator credits |
| [`wokwi/`](wokwi) | Wokwi simulator project (Pico + LED grid + two buttons, audio faked) and the script that generates it from `firmware/code.py` |

## Quick start

1. Wire it up following the [build guide](docs/build-guide.md#wiring-diagram).
2. Install CircuitPython 10.x on the board and copy `neopixel.mpy`, `adafruit_lis3dh.mpy` and `adafruit_bus_device/` into `CIRCUITPY/lib`.
3. Copy `firmware/code.py` and `firmware/safemode.py` to the root of `CIRCUITPY`.
4. Copy `audio/sounds/` (and, optionally, `audio/rain/`) to the root of `CIRCUITPY`. Your own clips must be 16-bit mono WAV at 22,050 Hz.
5. Tweak the settings block at the top of `code.py`. Rain is off until `USE_RAIN_BUTTON = True`.

## Status

The code has been checked on desktop simulations and on CircuitPython firmware in Wokwi's RP2040 emulator (lights and buttons). It has not yet run on the real Prop-Maker hardware, so do the bench test in the build guide before stuffing the cloud.

## Audio credits

Sound effects are from [Pixabay](https://pixabay.com/sound-effects/) under the Pixabay Content License; each creator is credited in [`audio/README.md`](audio/README.md).
