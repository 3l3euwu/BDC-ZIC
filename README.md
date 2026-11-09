# BDC-ZIC (experimental)

A **local** UE4SS mod that experiments with playing another Windows app's audio through a Bodycam Unreal audio component. It captures a selected process tree with Windows process loopback, converts stereo to mono, and feeds PCM to `SteamCoreProVoice`, a procedural Unreal sound wave. The component is attached near the local player's pawn, rather than played as a UI sound, so it enters the game's ordinary audio graph. Actual spatialization, attenuation, occlusion and reverb depend on Bodycam's current sound settings and have **not been verified**. This does not transmit music to other players or replace voice chat.

**Status: prototype, not tested in Bodycam or on Windows.** The reflection calls, SteamCorePro plugin availability, sample format and sound routing are version dependent. This may fail silently, stutter, or crash the game; use at your own risk and check the game's modding/online rules. It does not promise gunshot-identical processing. The Linux cross-build and a mocked Lua smoke test are the only checks performed.

## Requirements

- Windows x64, Windows 10 build 20348 or later (or Windows 11) for process loopback; Bodycam and a UE4SS build compatible with your game version (UE 5.5 builds commonly require an experimental UE4SS build).
- The game must expose `/Script/SteamCorePro.Default__SteamCoreProVoice`, `ConstructSteamCoreProVoice` and `AddAudioBuffer`. If the plugin is absent this prototype cannot play audio.
- Python 3 with Tkinter and the Windows Python launcher (`pyw.exe`) to run the panel, and Zig to build the helper. No Python packages, accounts, or network service needed.

## Build and install

1. Install Zig and run `powershell -ExecutionPolicy Bypass -File .\build.ps1` from the repository. This produces a ready-to-copy `dev-build\BDC_ZIC` folder, including `native\capture.exe`. A development build may already be present there; rebuild it after changing the source.
2. Copy the **whole** `dev-build\BDC_ZIC` folder to `Bodycam\Bodycam\Binaries\Win64\ue4ss\Mods\BDC_ZIC`. Enable it by adding `BDC_ZIC : 1` to `ue4ss\Mods\mods.txt` (or use your UE4SS mod manager). Keep the panel, helper and Scripts together.
3. Run `Open-Panel.vbs` in the installed mod folder (uses `pyw.exe` so no Python console is shown). Opening the panel also asks Steam to launch Bodycam via `steam://rungameid/2406770`; if Steam cannot launch, start the game manually. Enter a match and press **F7** to create the local emitter. Check the UE4SS console for `[BDC-ZIC]` errors. F7 again stops the emitter; after a map change restart it in the new match.
4. In the panel, select **Spotify** or **YoloTube / YouTube** in the app preset, choose a matching window (or use **All processes** / type a PID), and press **Start capture**. Start music in that app. Select the parent process if audio is produced by a child process; window-title matches do not guarantee that the window owner actually renders audio, and some browsers use audio service processes outside the selected tree. Refresh after opening or changing windows; if there are multiple matches, choose one explicitly. Use Stop or close the panel to stop capture.

## Live effects

The panel's sound-shaping switches and 1–10 sliders are applied by the capture helper before audio reaches Unreal. Changes are picked up during capture; settings persist in `%LOCALAPPDATA%\BDC-ZIC\stream\effects.ini`. All effects start disabled. Volume 5 is unity; 1 is quiet and 10 is double gain with hard clipping.

- **Reverb** adds a simple feedback echo; **Room size** adds early reflections and changes the delay length. These are synthetic effects, separate from any reverb the game may apply.
- **Distance** reduces volume and high frequencies; it does not move the Unreal emitter. **Muffle** is a low-pass filter; **Clarity** boosts high-frequency detail and can also emphasize noise.
- **Stereo input blend** chooses how much of the source's left versus right channel is mixed into mono: 1 favors left, 10 favors right. The game stream remains **mono**, so this is not stereo width or stereo output.

Settings are intentionally simple, not a physically accurate acoustic simulation. Audible results and performance in Bodycam remain untested. The panel requires the updated `capture.exe` from the same build; an older helper will ignore the controls.

## Important audio limitations

- **The music app is not muted.** Windows session mute also silences process loopback, so a naive mute would prevent capture. This prototype does not inject into other apps or change system routing. You may hear both the original app and the in-game emitter. A separate output device routed to the app and muted at the *endpoint* may work, but affects everything on that endpoint and is not managed by this project. Do not mute your main endpoint expecting only the app to be silenced.
- Playback is **local only**, anchored to the player's pawn, not replicated to other clients. It does not mix into the game's microphone/VOIP.
- The helper requests 48 kHz stereo PCM16, downmixes to mono PCM16, and publishes bounded 50 ms packets. UE4SS converts each packet into a Lua byte table on the game thread; performance, format acceptance and latency are unverified. Packet drops can occur under load. This is not a polished low-latency audio engine.
- The stream files and `capture.log` live under `%LOCALAPPDATA%\BDC-ZIC\stream` (or the mod folder if `LOCALAPPDATA` is unavailable). They contain recent raw audio; stop capture and delete this folder to remove them. Run only one panel/helper and one game instance per mod folder. Avoid selecting Bodycam itself, which can create feedback.
- If nothing plays, read `%LOCALAPPDATA%\BDC-ZIC\stream\capture.log` and the UE4SS console. The selected app must be actively outputting audio, and the correct process tree must be selected. Protected/sandboxed apps or Windows configurations may not produce capturable audio. Verify the app is not session-muted. No audio-routing or volume settings are modified.

## Development

`native/capture.cpp` is a standalone process-loopback producer; `mod/BDC_ZIC/Scripts/main.lua` is the Unreal-side consumer and `mod/BDC_ZIC/panel/panel.py` is the Tk controller. The fixed eight-slot file buffer bounds disk use but intentionally favors freshness over lossless delivery. `tests/mod_smoke.lua` mocks the UE4SS API and can be run with Lua 5.4 from the repository root; it is not an integration test. Do not interpret successful compilation or the smoke test as proof that the game integration works.
