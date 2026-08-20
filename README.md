# bw-headphones

An Omarchy Quickshell bar widget for Bowers & Wilkins Px7 S3 headphones.

## Features

- Battery and charging state.
- Bluetooth connection state.
- Active PipeWire output information when available.
- ANC, Pass-Through, and Off controls.
- Keyboard-friendly popup matching Omarchy’s panel style.
- Graceful fallback when vendor control is unavailable.

## Requirements

- Omarchy 4 / Quickshell 0.3.
- BlueZ and PipeWire.
- Python 3 and PyGObject (`python-gobject`) for the D-Bus bridge.
- A paired Bowers & Wilkins Px7 S3.

## Install

```sh
omarchy plugin add https://github.com/PatrikHallgren/bw-headphones.git --enable
~/.config/omarchy/plugins/io.github.patrikhallgren.bw-headphones/setup
```

The plugin runs as a user service and does not require root access. Pair the
Px7 S3 using Omarchy’s Bluetooth panel first.

## Configuration

The default behavior is to show the widget only while a Px7 S3 is connected.
The plugin settings can override that behavior or select a device explicitly:

```json
{
  "hideWhenDisconnected": true,
  "deviceAddress": "AA:BB:CC:DD:EE:FF",
  "ctlPath": "px7s3ctl"
}
```

Pairing, connect/disconnect, output selection, and system volume remain in
Omarchy’s stock Bluetooth and Audio panels.

The setup script also installs a device-specific WirePlumber rule for Px7 S3
devices. It selects SBC on reconnect because this headset was silent with
aptX HD on the tested system. Other Bluetooth devices are not affected.

## Keyboard controls

Left-click opens the panel. Right-click cycles ANC modes.

```text
j/k or arrows  Navigate
Enter/Space    Activate
o              Noise cancellation off
p              Pass-through
n              Noise cancellation
r              Refresh
Tab            Next Omarchy panel
Escape         Close
```

## Troubleshooting

- Run `px7s3ctl status --json` and check `last_error` and `transport_ready`.
- If the widget is missing, run `omarchy-shell shell rescanPlugins` and make
  sure `io.github.patrikhallgren.bw-headphones` is enabled in the right bar.
- Inspect the daemon with
  `systemctl --user status io.github.patrikhallgren.bw-headphones.service`.
- Vendor control is disabled when the required B&W GATT characteristics or a
  supported reply are not present.

## Protocol limitations

The B&W control transport is based on clean-room live observations and the
published Px7 S3 user-facing behavior. It discovers the request, response,
and optional notification characteristics at runtime and probes only safe
read commands. Firmware updates, DFU, factory reset, pairing-list mutation,
and other destructive operations are not implemented.

The current hardware-validated reference is Px7 S3 firmware **3.17.4.17**.
Other firmware versions and Bowers & Wilkins models must be verified before
being treated as supported.

## Privacy and permissions

The daemon runs as the logged-in user. It reads BlueZ device and GATT state,
reads local PipeWire information through Quickshell, writes one status file
under `$XDG_STATE_HOME/bw-headphones/`, and accepts commands only through a
mode-0600 socket under `$XDG_RUNTIME_DIR`. It does not contact a network
service or collect telemetry.

## Development and hardware testing

Development prerequisites include Python 3, PyGObject, Deno, Rust/Cargo for
the protocol test crate, Omarchy 4, Quickshell 0.3, and the Qt development
package that provides `qmllint`.

```sh
deno test tests/
python3 tests/protocol.test.py
cargo test --manifest-path helper/Cargo.toml
omarchy plugin validate .
qmllint -I "$OMARCHY_PATH/shell" Panel.qml Service.qml
```

Hardware testing should cover pairing/reconnect, battery and charging
updates, all three ANC modes, physical headphone changes, Bluetooth
off/on/out-of-range behavior, A2DP and Hands-Free profiles, multipoint,
USB-C and 3.5 mm wired modes, and daemon restart while Quickshell remains
running. Record the exact firmware version with every support report.

## Helper commands

```sh
px7s3ctl status --json
px7s3ctl refresh
px7s3ctl set-anc off
px7s3ctl set-anc anc
px7s3ctl set-anc pass-through
```

The helper publishes state at
`$XDG_STATE_HOME/bw-headphones/status.json` and exposes a user-only Unix
socket. It never implements firmware updates, factory reset, DFU, or pairing
list mutation.

## Uninstall

```sh
./uninstall
omarchy plugin remove io.github.patrikhallgren.bw-headphones
```

## License

MIT. The Px7 S3 and Bowers & Wilkins names are trademarks of their respective
owner. This project is not affiliated with Bowers & Wilkins.
