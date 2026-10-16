"""Raspberry Pi 5 GPIO access via gpiozero with an explicit lgpio factory.

Why lgpio: the Pi 5 routes its 40-pin header through the RP1 southbridge.
``RPi.GPIO`` does not support RP1; ``lgpio`` (the default backend of gpiozero on
Raspberry Pi OS Bookworm) uses the Linux GPIO character device and works on the
Pi 5. Install ``python3-gpiozero`` and ``python3-lgpio``; create the virtualenv with
``--system-site-packages`` so it is importable.

Outputs and PWM use gpiozero; inputs and echo edge timestamps use lgpio directly
on separate lines of the same controller. All access goes through :class:`GpioChip`. Web routes,
database code and callbacks never touch pins directly.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class HardwareInitError(RuntimeError):
    """A real hardware device could not be initialised. Never silently replaced by simulation."""


def _import_lgpio() -> Any:
    try:
        import lgpio  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on platform
        raise HardwareInitError(
            "lgpio is not installed. On Raspberry Pi OS: 'sudo apt install python3-lgpio' "
            "and create the venv with --system-site-packages."
        ) from exc
    return lgpio


PULL_FLAGS = {"up": "SET_PULL_UP", "down": "SET_PULL_DOWN", "none": "SET_PULL_NONE"}


def _import_gpiozero() -> tuple[Any, Any, Any]:
    try:
        from gpiozero import DigitalOutputDevice, PWMOutputDevice
        from gpiozero.pins.lgpio import LGPIOFactory
    except ImportError as exc:
        raise HardwareInitError(
            "gpiozero/lgpio is not installed. On Raspberry Pi OS: "
            "'sudo apt install python3-gpiozero python3-lgpio' and create the "
            "venv with --system-site-packages."
        ) from exc
    return DigitalOutputDevice, PWMOutputDevice, LGPIOFactory


class GpioChip:
    """Owns the gpiochip handle and tracks claimed lines so they are released on close."""

    def __init__(self, chip: int | str = "auto") -> None:
        self._requested = chip
        self._lg: Any = None
        self.handle: int | None = None
        self.chip_number: int | None = None
        self.label: str | None = None
        self._claimed: set[int] = set()
        self._outputs: dict[int, Any] = {}
        self._factory: Any = None
        self._digital_type: Any = None
        self._pwm_type: Any = None
        self._lock = threading.RLock()

    @property
    def lg(self) -> Any:
        if self._lg is None:
            raise HardwareInitError("GPIO chip not opened")
        return self._lg

    def open(self) -> None:
        with self._lock:
            if self.handle is not None:
                return
            lg = _import_lgpio()
            # Enumerate actual devices: RP1 numbering is a kernel detail.
            candidates = ([self._requested] if self._requested != "auto" else
                          sorted(int(p.name.removeprefix("gpiochip"))
                                 for p in Path("/dev").glob("gpiochip[0-9]*")
                                 if p.name.removeprefix("gpiochip").isdigit()))
            last_error: Exception | None = None
            for n in candidates:
                try:
                    h = lg.gpiochip_open(int(n))
                except Exception as exc:  # lgpio.error
                    last_error = exc
                    continue
                try:
                    info = lg.gpio_get_chip_info(h)
                    label = " ".join(str(v) for v in info[2:4])
                except Exception as exc:
                    last_error = exc
                    lg.gpiochip_close(h)
                    continue
                # Never select a different controller merely because its name
                # contains pinctrl: on Pi 5 those offsets are not header BCM pins.
                if self._requested == "auto" and "rp1" not in label.lower():
                    lg.gpiochip_close(h)
                    continue
                self._lg, self.handle, self.chip_number, self.label = lg, h, int(n), label
                log.info("opened gpiochip%s (%s)", n, label)
                return
            raise HardwareInitError(f"could not open a Raspberry Pi GPIO chip ({last_error or 'no RP1 chip found'})")

    def claim_output(self, pin: int, level: int = 0) -> None:
        with self._lock:
            self._check_unclaimed(pin)
            self._output_factory()
            self._outputs[pin] = self._digital_type(
                pin, initial_value=bool(level), pin_factory=self._factory)

    def _output_factory(self) -> None:
        if self.handle is None:
            raise HardwareInitError("GPIO chip not opened")
        if self._factory is None:
            digital, pwm, factory = _import_gpiozero()
            # Explicit factory prevents environment/default fallback to RPi.GPIO,
            # native pins, remote GPIO, or mock pins in real hardware mode.
            self._factory = factory(chip=self.chip_number)
            self._digital_type, self._pwm_type = digital, pwm

    def claim_pwm(self, pin: int, frequency_hz: int) -> None:
        with self._lock:
            self._check_unclaimed(pin)
            self._output_factory()
            self._outputs[pin] = self._pwm_type(
                pin, initial_value=0, frequency=frequency_hz, pin_factory=self._factory)

    def claim_input(self, pin: int, pull: str = "none") -> None:
        with self._lock:
            self._check_unclaimed(pin)
            flag = getattr(self.lg, PULL_FLAGS[pull])
            self.lg.gpio_claim_input(self.handle, pin, flag)
            self._claimed.add(pin)

    def claim_alert(self, pin: int, pull: str = "none") -> None:
        with self._lock:
            self._check_unclaimed(pin)
            flag = getattr(self.lg, PULL_FLAGS[pull])
            self.lg.gpio_claim_alert(self.handle, pin, self.lg.BOTH_EDGES, flag)
            self._claimed.add(pin)

    def _check_unclaimed(self, pin: int) -> None:
        if pin in self._outputs or pin in self._claimed:
            raise HardwareInitError(f"GPIO {pin} already claimed")

    def write(self, pin: int, level: int) -> None:
        with self._lock:
            self._outputs[pin].value = 1 if level else 0

    def read(self, pin: int) -> int:
        return int(self.lg.gpio_read(self.handle, pin))

    def pwm(self, pin: int, frequency_hz: int, duty_percent: float) -> None:
        duty = max(0.0, min(100.0, duty_percent))
        with self._lock:
            output = self._outputs[pin]
            if output.frequency != frequency_hz:
                output.frequency = frequency_hz
            output.value = duty / 100.0

    def callback(self, pin: int, func: Any) -> Any:
        return self.lg.callback(self.handle, pin, self.lg.BOTH_EDGES, func)

    def free(self, pin: int) -> None:
        with self._lock:
            output = self._outputs.pop(pin, None)
            if output is not None:
                try:
                    try:
                        output.off()
                    finally:
                        output.close()
                except Exception:
                    log.exception("failed to close GPIO output %s", pin)
            if pin in self._claimed and self.handle is not None:
                try:
                    self.lg.gpio_free(self.handle, pin)
                except Exception:  # pragma: no cover
                    log.exception("failed to free GPIO %s", pin)
                self._claimed.discard(pin)

    def close(self) -> None:
        with self._lock:
            if self.handle is None:
                return
            for pin in list(self._outputs):
                self.free(pin)
            for pin in list(self._claimed):
                self.free(pin)
            try:
                self.lg.gpiochip_close(self.handle)
            finally:
                self.handle = None
                if self._factory is not None:
                    self._factory.close()
                    self._factory = None


class LazyGpio:
    """Opens the chip only when the first real device asks for it."""

    def __init__(self, chip: int | str) -> None:
        self._chip = GpioChip(chip)
        self.opened = False

    def get(self) -> GpioChip:
        if not self.opened:
            self._chip.open()
            self.opened = True
        return self._chip

    def close(self) -> None:
        if self.opened:
            self._chip.close()
            self.opened = False
