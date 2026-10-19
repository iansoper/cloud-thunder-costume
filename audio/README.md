# Audio

This folder mirrors the board's drive: copy `sounds/` (and `rain/`, if you use the rain button) to the root of `CIRCUITPY`.

Every file must be **16-bit mono WAV at 22,050 Hz**; the code skips anything else. Keep the total under about 6 MB.

| Folder | Plays when |
| --- | --- |
| `sounds/` | Thunder: one random clip per strike |
| `rain/` | Rain loop: toggled by the green button (`USE_RAIN_BUTTON = True`) |

## Credits

All sounds come from [Pixabay](https://pixabay.com/sound-effects/search/thunder/) under the [Pixabay Content License](https://pixabay.com/service/license-summary/). Attribution isn't required, but the creators are credited here. Files keep Pixabay's creator name and sound ID in their names.

| File | Sound | Creator | Pixabay ID |
| --- | --- | --- | --- |
| `sounds/07.pwlpl-loud-thunder-sound-effect-359269.wav` | [Loud Thunder Sound Effect](https://pixabay.com/sound-effects/loud-thunder-sound-effect-359269/) | [PWLPL](https://pixabay.com/users/pwlpl-16464651/) | 359269 |
