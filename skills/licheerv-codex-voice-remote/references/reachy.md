# Optional PC → Reachy bridge

The PC receiver can send voice lifecycle events to a separate Reachy bridge at localhost port 8766. It is optional and does not carry WAV audio or Codex text. The bridge template includes reachy_bridge.py, reachy_config.example.json, and start_reachy_bridge.ps1.

To enable it, create a private reachy_config.json with a long random token, start the bridge in dry_run mode, and set the same token plus the localhost URL in the private PC config. GET http://127.0.0.1:8766/health reports its state. The receiver emits listening, thinking, acknowledge, and neutral events. If it is not installed, leave reachy_bridge_url and reachy_bridge_token empty in pc_config.json; the voice link works without it.

For real robot motion, use the separate reachy-mini-codex-bridge skill and verify the hardware state before changing dry_run mode. Do not package real Reachy tokens or the live config.
