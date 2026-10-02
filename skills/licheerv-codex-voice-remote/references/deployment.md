# Deploy and verify the board → PC → Codex link

## Files and roles

- Board: board_client.py, board_config.json, and S99-codex-voice under /root/codex-remote. USER key events come from the configured /dev/input/event device; arecord captures mono 16-bit WAV.
- Windows PC: pc_server.py, codex_desktop.py, pc_config.json, and the SenseVoiceSmall int8 ONNX model. The PC performs ASR and Codex Desktop UI automation.
- Optional Reachy: a separate localhost bridge on port 8766. Leave its PC URL and token empty when unused.

The asset template contains only examples and source. Do not package live JSON configurations or token values. On the known installation the project is under C:\Users\15pro\Desktop\荔枝派Codex遥控器. Discover the actual path before acting elsewhere.

## Initial PC setup

1. Copy assets/bridge-template to the intended project directory.
2. Run setup_pc.ps1. It creates a virtual environment, installs the PC requirements, downloads SenseVoiceSmall int8 if absent, and creates pc_config.json with a random token. It does not download Whisper.
3. Keep pc_config.json private. Verify listen_host and port. Port 8765 should be reachable from the board on a trusted USB or local network.
4. Start start_pc.ps1. Keep Codex Desktop open with a composer available.
5. Check http://127.0.0.1:8765/health from the PC. If PowerShell routes localhost through a proxy, use Invoke-WebRequest with -Proxy $null.

On the known USB NCM connection, the PC has 10.233.141.100 and the board has 10.233.141.1. These are examples. Use ipconfig on Windows and ip addr on the board to discover current addresses. For Wi-Fi use the PC's reachable LAN address and verify client isolation is off.

## Board setup

1. Copy board_client.py, board_config.example.json, and board_tools/S99-codex-voice to /root/codex-remote. Copy the example JSON to board_config.json on the board.
2. Set server_url to the PC address and port. Set token to the same token as pc_config.json without printing either value. Confirm audio_device, audio_mixer_device, USER event path, and key code against this board image.
3. From the board, request the PC /health endpoint. Run board_client.py --user-key-voice manually first.
4. Hold USER while speaking for at least 0.2 second and release. Check the PC panel at http://127.0.0.1:8765/ or the local /api/state endpoint. Confirm receipt, transcription, and Codex insertion.
5. After a manual success, install S99-codex-voice in /etc/init.d, make it executable, and start it. The service writes /var/log/codex-user-key-voice.log. It supports start and stop; use stop followed by start when a restart is needed.

The template also supports three optional external GPIO controls in the non-USER mode. Do not enable them until the exact pinmux and GPIO numbers have been verified on the hardware.

## Protocol and expected results

- GET /health returns {"ok":true}; it does not require authentication and proves only the PC listener.
- GET / and GET /api/state are local-PC-only. The state endpoint shows recent events and the last transcript.
- POST /audio carries the WAV. POST /event carries JSON with button approve or deny for verified external buttons. Both require X-Bridge-Token and a unique X-Event-Id. The receiver deduplicates retried IDs.
- The board sender retries temporary network errors up to three times. HTTP errors are not retried. The receiver accepts mono 16-bit WAV at 16 or 48 kHz, 0.2–30 seconds, up to 10 MiB. The board normally records at 48 kHz and caps at 20 seconds.
- Ordinary dictated text is inserted and remains for review. Exact 开始 submits the composer; exact 取消 clears it. Longer phrases are text.

## Diagnose in link order

1. PC listener: check its process, /health, selected listen address and port, and firewall on the board-facing network.
2. Board route: confirm the board can reach the PC address in board_config.json. Check /var/log/codex-user-key-voice.log for upload response. A 401 means authentication mismatch; a 400 can indicate malformed WAV or missing event ID.
3. Capture: verify arecord -l, ALSA device, capture volume, and a short local WAV. A recording under 0.2 second is rejected by design.
4. ASR: check that the SenseVoice ONNX model and tokens.txt exist and the PC event panel reports transcription.
5. Codex insertion: if transcription exists but no text appears, bring the intended Codex Desktop window forward, close extra windows, and run inspect_codex_ui.py to inspect labels. Adjust button_labels or composer_labels only from observed UI evidence.
6. Optional Reachy: timeouts to port 8766 do not imply voice failure. Use references/reachy.md only if robot interaction is in scope.
