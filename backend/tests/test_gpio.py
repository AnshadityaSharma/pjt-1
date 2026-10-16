"""Pi 5 boundaries exercised without installing GPIO libraries on the host."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rover.config import MotorConfig, UltrasonicSensorConfig
from rover.hal import gpio
from rover.hal.motors import L298NMotorDriver
from rover.sensors.base import SensorInitError
from rover.sensors.drivers.gpio_drivers import HcSr04


@pytest.fixture
def lg(monkeypatch):
    library = Mock()
    library.gpiochip_open.side_effect = lambda n: n + 100
    library.gpio_get_chip_info.side_effect = lambda h: (
        0, 54, f"gpiochip{h - 100}", "pinctrl-rp1" if h == 107 else "pinctrl-bcm2712")
    monkeypatch.setattr(gpio, "_import_lgpio", lambda: library)
    monkeypatch.setattr(gpio.Path, "glob", lambda *_: [Path("/dev/gpiochip0"), Path("/dev/gpiochip7")])
    return library


def test_auto_selects_rp1_beyond_old_fixed_chip_list(lg):
    chip = gpio.GpioChip()
    chip.open()
    assert chip.chip_number == 7
    lg.gpiochip_close.assert_called_once_with(100)
    chip.close()
    assert lg.gpiochip_close.call_args.args == (107,)


def test_auto_refuses_non_header_controller(lg):
    lg.gpio_get_chip_info.return_value = (0, 54, "gpiochip0", "pinctrl-bcm2712")
    lg.gpio_get_chip_info.side_effect = None
    with pytest.raises(gpio.HardwareInitError, match="no RP1"):
        gpio.GpioChip().open()
    assert lg.gpiochip_close.call_count == 2


def test_chip_info_failure_releases_probe_handle(lg):
    lg.gpio_get_chip_info.side_effect = RuntimeError("permission denied")
    with pytest.raises(gpio.HardwareInitError, match="permission denied"):
        gpio.GpioChip().open()
    assert lg.gpiochip_close.call_count == 2


def test_explicit_chip_is_honoured(lg):
    chip = gpio.GpioChip(0)
    chip.open()
    assert chip.chip_number == 0
    chip.close()


def test_motor_outputs_use_explicit_factory_and_start_stopped(lg, monkeypatch):
    factory = Mock()
    digital, pwm, factory_type = Mock(), Mock(), Mock(return_value=factory)
    outputs = {}

    def device(pin, **kwargs):
        assert kwargs["pin_factory"] is factory
        assert kwargs["initial_value"] == 0
        outputs[pin] = Mock(value=0, frequency=kwargs.get("frequency"))
        return outputs[pin]

    digital.side_effect = pwm.side_effect = device
    monkeypatch.setenv("GPIOZERO_PIN_FACTORY", "mock")
    monkeypatch.setattr(gpio, "_import_gpiozero", lambda: (digital, pwm, factory_type))
    lazy = gpio.LazyGpio("auto")
    driver = L298NMotorDriver(MotorConfig(driver="l298n"), lazy)
    driver.initialize()
    factory_type.assert_called_once_with(chip=7)
    assert digital.call_count == 4 and pwm.call_count == 2
    driver.set_outputs(0.5, -0.5)
    assert outputs[17].value == 1 and outputs[27].value == 0
    assert outputs[22].value == 0 and outputs[23].value == 1
    assert outputs[12].value == pytest.approx(0.65)
    driver.stop()
    assert outputs[12].value == outputs[13].value == 0
    driver.close()
    assert all(o.close.call_count == 1 for o in outputs.values())
    lazy.close()
    factory.close.assert_called_once()


def test_partial_motor_setup_releases_claims():
    chip = Mock()
    chip.claim_pwm.side_effect = RuntimeError("PWM unavailable")
    driver = L298NMotorDriver(MotorConfig(driver="l298n"), Mock(get=Mock(return_value=chip)))
    with pytest.raises(gpio.HardwareInitError, match="PWM unavailable"):
        driver.initialize()
    assert chip.free.call_count == 6
    assert not driver.initialized and driver._chip is None


def test_partial_ultrasonic_setup_releases_claims():
    chip = Mock()
    chip.callback.side_effect = RuntimeError("edge unavailable")
    sensor = HcSr04(
        UltrasonicSensorConfig(id="front_ultrasonic", driver="hcsr04", trigger_pin=24, echo_pin=25),
        SimpleNamespace(gpio=Mock(get=Mock(return_value=chip))),
    )
    with pytest.raises(SensorInitError, match="edge unavailable"):
        sensor.initialize()
    assert {call.args[0] for call in chip.free.call_args_list} == {24, 25}
    assert sensor.chip is None


def test_lazy_gpio_does_not_import_hardware_until_requested(monkeypatch):
    load = Mock(side_effect=gpio.HardwareInitError("lgpio missing"))
    monkeypatch.setattr(gpio, "_import_lgpio", load)
    lazy = gpio.LazyGpio("auto")
    load.assert_not_called()
    lazy.close()
    with pytest.raises(gpio.HardwareInitError, match="lgpio missing"):
        lazy.get()
    assert not lazy.opened


def test_missing_gpiozero_fails_without_claiming_output(lg, monkeypatch):
    chip = gpio.GpioChip()
    chip.open()
    monkeypatch.setattr(gpio, "_import_gpiozero", Mock(side_effect=gpio.HardwareInitError("gpiozero missing")))
    with pytest.raises(gpio.HardwareInitError, match="gpiozero missing"):
        chip.claim_output(17)
    assert not chip._outputs
    chip.close()


def test_echo_callback_preserves_nanosecond_width():
    sensor = HcSr04(UltrasonicSensorConfig(id="front_ultrasonic"), SimpleNamespace())
    sensor._edge(7, 25, 1, 1_000_000_000)
    sensor._edge(7, 25, 0, 1_001_000_000)
    assert sensor._width_ns == 1_000_000
    assert sensor._done.is_set()
