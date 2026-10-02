---
name: licheerv-codex-voice-remote
description: Deploy, start, verify, and troubleshoot the LicheeRV Nano-W USER-key voice link to Codex Desktop through a Windows PC. Use for board networking, WAV upload, local SenseVoice transcription, and Codex composer actions; use the separate Reachy skill for robot motion.
---

# LicheeRV Nano-W → Codex voice link

The tested path is: hold the board USER key → record from ALSA → send WAV over USB NCM or Wi-Fi to the PC receiver → transcribe locally with SenseVoiceSmall int8 on the PC CPU → operate the visible Codex Desktop composer. The board does not run the speech model. The deployable files are in assets/bridge-template. The current local installation is under C:\Users\15pro\Desktop\荔枝派Codex遥控器; discover its actual location before acting on another machine.

The template intentionally installs only SenseVoice. It contains no model weights, authentication tokens, saved recordings, or machine-specific configuration. setup_pc.ps1 downloads the model when needed. Never copy real pc_config.json, board_config.json, reachy_config.json, logs, WAV files, downloaded models, or CUDA files into a skill or Git repository.

## Choose the relevant procedure

- For setup, activation, network checks, credentials, service state, and end-to-end verification, read references/deployment.md.
- For USER key, ALSA device, pinmux, or optional external button wiring, read references/hardware.md. USER is the default tested control; do not invent GPIO numbers.
- For optional PC → Reachy status signals, read references/reachy.md. Robot actions remain governed by the separate reachy-mini-codex-bridge skill.

## Operational invariants

- Confirm the PC receiver is listening and its /health endpoint returns ok before diagnosing speech recognition. Then confirm the board can reach the PC address in board_config.json. The USB NCM addresses 10.233.141.100 and 10.233.141.1 are examples from one installation, not universal defaults.
- The PC and board must share the same long random token. Read tokens only into process memory; do not print, commit, or place them in command text, logs, or chat. Check authentication through the supported request headers rather than displaying token hashes.
- Hold USER while speaking and release to upload. An utterance consisting only of 开始, with optional whitespace or punctuation, submits the current composer. 取消 alone clears it. All other text, including 开始开始 and 开始写代码, is dictated into the composer for review.
- Codex Desktop UI automation needs an available composer. If more than one Codex window is visible, keep the intended one in front. If ASR succeeds but text is not inserted, inspect the UI labels before changing the model.
- Treat optional Reachy errors as a separate side-channel issue when audio and Codex insertion still work. Leave the Reachy URL and token empty if that bridge is unused.
- Verify a change with observable evidence: PC /health, board reachability, a USER-key recording received, transcription, and Codex insertion or exact command action. A successful /health response alone does not prove the microphone path.
