# Nano-W hardware reference

## Tested control

Use the board USER key as the hold-to-talk button. The client listens to an input-event device and records only while the key is pressed. This avoids uncertain header GPIO muxing and uses a switch already present on the board.

## Wi-Fi edition header constraints

On LicheeRV Nano-W, GPIO P18 through P23 are connected to the Wi-Fi module SDIO interface and GPIO A26 is Wi-Fi enable. Do not use those pins for application buttons or LEDs.

GPIO A18, A19, A28, and A29 are connected to the Wi-Fi module Bluetooth interface through an optional resistor network that is normally not populated. They can be defined by the user on the Wi-Fi edition when Bluetooth has not been enabled with that resistor network. Verify pinmux and the Linux GPIO number on the running image before depending on them.

The eMMC labels in the pinout describe alternate SoC functions. They do not mean that the Nano-W always has onboard eMMC; the board boot and storage configuration can use microSD instead.

## Button wiring

For an external active-low button:

```text
GPIO ── button ── GND
```

Configure the GPIO as input with pull-up. The unpressed state reads high; the pressed state reads low. If using an LED too, connect it as a separate parallel branch from the GPIO node, not in series with the button:

```text
GPIO ── button ── GND
  └── LED ─ resistor ── GND
```

A bare LED should not be connected directly between 3.3 V and GND or between a driven GPIO and GND. Use a series resistor, normally around 1 kΩ at 3.3 V. Internal pull-up/down resistors are typically tens of kilo-ohms and only produce a faint LED; they are suitable for input biasing, not for powering an indicator.

## Pin validation

Before assigning an application function:

1. Check the board pinout and Wi-Fi edition reservations.
2. Check the device-tree pinmux and the corresponding Linux GPIO number.
3. Read the input level while pressing the physical button.
4. Only then add it to the persistent board client configuration.

Avoid pins that are part of boot, storage, Wi-Fi SDIO, Wi-Fi enable, or another active peripheral.
