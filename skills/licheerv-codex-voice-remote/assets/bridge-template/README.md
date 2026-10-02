# LicheeRV Nano-W voice remote for Codex Desktop

This template connects the board's USER key and microphone to a Windows PC running Codex Desktop:

    USER held → ALSA WAV → USB NCM or Wi-Fi → PC receiver :8765
             → local SenseVoiceSmall int8 on CPU → Codex composer

The board only records and uploads audio. The PC performs speech recognition. Exact 开始 submits the current composer; exact 取消 clears it. Other speech is pasted for review. Optional external GPIO buttons can send approve or deny events after their pins have been validated.

## Included files

- board_client.py and board_tools/S99-codex-voice: board capture, upload, and boot service.
- pc_server.py and codex_desktop.py: authenticated PC receiver and Codex UI automation.
- setup_pc.ps1 and start_pc.ps1: Windows setup and start.
- pc_config.example.json and board_config.example.json: configuration templates; real config files stay private.
- inspect_codex_ui.py and test_bridge.py: diagnostics and local protocol checks.
- reachy_bridge.py, reachy_config.example.json, and start_reachy_bridge.ps1: optional local Reachy status bridge, initially dry_run.

The repository does not contain model weights, real tokens, WAV recordings, logs, or downloaded runtime files.

## Install

1. On Windows, run setup_pc.ps1 in this folder. It installs the dependencies, downloads the SenseVoiceSmall int8 ONNX model, and generates pc_config.json with a random token.
2. Review pc_config.json and start start_pc.ps1. With Codex Desktop visible, check http://127.0.0.1:8765/health.
3. On the board, copy board_client.py, board_config.example.json, and S99-codex-voice into /root/codex-remote. Copy the example JSON to board_config.json and set the PC server URL, the matching token, actual ALSA device, and USER event device.
4. Check the board can reach the PC /health endpoint. Run python3 board_client.py --user-key-voice manually. Hold USER, speak, and release. The PC panel at http://127.0.0.1:8765/ shows receipt and transcription.
5. When the manual test works, install S99-codex-voice in /etc/init.d and start it. Its log is /var/log/codex-user-key-voice.log.

The previously tested USB NCM addresses are PC 10.233.141.100 and board 10.233.141.1. Discover the actual addresses on the target machine; Wi-Fi deployments use different addresses. Do not expose port 8765 to the internet.

## Voice behavior

- 开始 alone, optionally with punctuation or whitespace: submit the current composer.
- 取消 alone: clear the composer.
- Any other phrase, including 开始开始: paste text without submitting it.

If speech is recognized but Codex receives no text, inspect the currently visible Codex window with inspect_codex_ui.py. More detailed setup and troubleshooting is in the skill references/deployment.md when this template is used through the Codex skill.
