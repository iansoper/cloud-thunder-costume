# Thunder Cloud — runs only if CircuitPython drops into safe mode.
# After a power dip (brownout) or a crash, restart normally instead of
# sitting dark for the rest of the night.
import microcontroller
import supervisor

if supervisor.runtime.safe_mode_reason in (
    supervisor.SafeModeReason.BROWNOUT,
    supervisor.SafeModeReason.HARD_FAULT,
    supervisor.SafeModeReason.WATCHDOG,
):
    microcontroller.reset()
