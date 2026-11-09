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
3. Run `Open-Panel.vbs` in the installed mod folder (uses `pyw.exe` so no Python console is shown). Opening the panel also asks Steam to launch Bodycam via `steam://rungameid/2406770`; if Steam cannot launch, start the game manually. The emitter starts automatically when a local player is available and reconnects after a lobby or map change. **F7** toggles automatic playback off or back on. Check the UE4SS console for `[BDC-ZIC]` errors.
4. In the panel, select **Spotify** or **YoloTube / YouTube** in the app preset, choose a matching window (or use **All processes** / type a PID), and press **Start capture**. Start music in that app. Select the parent process if audio is produced by a child process; window-title matches do not guarantee that the window owner actually renders audio, and some browsers use audio service processes outside the selected tree. Refresh after opening or changing windows; if there are multiple matches, choose one explicitly. Use Stop or close the panel to stop capture.

## Live effects

The panel's sound-shaping switches and 1–10 sliders are applied by the capture helper before audio reaches Unreal. Changes are picked up during capture; settings persist in `%LOCALAPPDATA%\BDC-ZIC\stream\effects.ini`. All effects start disabled. Volume 5 is unity; 1 is quiet and 10 is double gain with hard clipping.

- **Reverb** adds a simple feedback echo; **Room size** adds early reflections and changes the delay length. These are synthetic effects, separate from any reverb the game may apply.
- **Distance** reduces volume and high frequencies; it does not move the Unreal emitter. **Muffle** is a low-pass filter; **Clarity** boosts high-frequency detail and can also emphasize noise.
- **Stereo input blend** chooses how much of the source's left versus right channel is mixed into mono: 1 favors left, 10 favors right. The game stream remains **mono**, so this is not stereo width or stereo output.

Settings are intentionally simple, not a physically accurate acoustic simulation. Audible results and performance in Bodycam remain untested. The panel requires the updated `capture.exe` from the same build; an older helper will ignore the controls.

### Experimental automatic room estimate

Enable **Auto room from game** in the panel. While the emitter is active, the mod measures nearby collision geometry about every **0.5 seconds** using four horizontal traces and one upward trace, up to 20 m each. Opposing horizontal distances estimate an average room width/depth; a ceiling and at least two wall hits are required to treat the space as enclosed. The panel shows the estimated span and applies synthetic reverb in near real time (game and UI scheduling can add latency): rooms up to about 4 m are dry, while progressively larger spaces receive more reverb. Open or insufficiently enclosed areas are dry.

The automatic setting overrides synthetic **reverb**, **room size**, and **distance**; the distance effect is an artificial low-pass/volume adjustment based on the estimated span, not the actual physical distance to the player or a moved emitter; other controls remain manual. Your manual settings remain saved as a fallback. Turning auto off, losing the estimate, or an estimate older than three seconds restores them.

This is an **opt-in approximation from collision geometry**, not a reading of Bodycam's actual room-size, gunshot, material, occlusion, or reverb settings. It does not hook or duplicate gunfire, and UE audio may add its own processing on top. Collision channels, open doors, moving objects, and trace compatibility can make the estimate misleading; it can add overhead or fail in a particular game/UE4SS build. Check the panel status and `[BDC-ZIC]` log; disable it if it causes issues. Not tested in Bodycam.

### Route your music app to a separate output

1. Connect or install a second **playback/output** device (for example a spare USB headset or a virtual audio cable). Leave your normal speakers/headset as the Windows default; use that normal output for Bodycam.
2. Start playing music so the app appears in Windows audio settings. In the BDC-ZIC panel click **Windows app audio settings**. On Windows 11, go to **Settings → System → Sound → Volume mixer**; under **Apps**, expand your music app and choose the second device under **Output device**. On Windows 10, use **Settings → System → Sound → Advanced sound options → App volume and device preferences** and choose the app's **Output**. Names vary by Windows version.
3. Keep the app's volume up and its app/session mute **off**. If output doesn't move, restart the music app and check its output selection again. Some browsers use separate audio processes; choose the correct process in the panel.
4. In BDC-ZIC, click **Find outputs**, select that same secondary device, check **Mute a dedicated output while capturing**, then click **Start capture** and confirm. This mutes **every app on that device**, not only the music app. Capture then feeds the game if Windows supports loopback from the muted endpoint.

If no secondary playback device exists, one is required for this method. Do not select Bodycam or route it to the muted output. The helper refuses Windows default endpoints. Normal stop restores the device's previous mute state, but after a crash check Windows Sound settings and unmute it manually if needed.

## Important audio limitations

- **Optional original-output mute requires a separate output device.** In the panel, open **Windows app audio settings** and route only the music app to a secondary physical or virtual output (restart the app if needed). Keep Bodycam on your normal output. Click **Find outputs**, choose that secondary device, enable **Mute a dedicated output while capturing**, then start capture and confirm. The mod cannot route the app for you or verify the route; all apps on the selected endpoint will be silenced. Default Windows output devices are rejected. Windows session/app mute cannot be used here because it also silences process loopback.
- The helper remembers the endpoint's previous mute state and restores it on normal stop or when the panel exits; it also stops and restores if the endpoint becomes a default output. If the helper or computer crashes, restoration is not guaranteed: manually unmute that device in Windows Sound settings. Do not use a device shared by other apps. Some Windows configurations or apps may still produce silence in capture when an endpoint is muted; this path is experimental and not tested on Windows.
- Playback is **local only**, anchored to the player's pawn, not replicated to other clients. It does not mix into the game's microphone/VOIP.
- The helper requests 48 kHz stereo PCM16, downmixes to mono PCM16, and publishes bounded 50 ms packets. UE4SS converts each packet into a Lua byte table on the game thread; performance, format acceptance and latency are unverified. Packet drops can occur under load. This is not a polished low-latency audio engine.
- The stream files and `capture.log` live under `%LOCALAPPDATA%\BDC-ZIC\stream` (or the mod folder if `LOCALAPPDATA` is unavailable). They contain recent raw audio; stop capture and delete this folder to remove them. Run only one panel/helper and one game instance per mod folder. Avoid selecting Bodycam itself, which can create feedback.
- If nothing plays, read `%LOCALAPPDATA%\BDC-ZIC\stream\capture.log` and the UE4SS console. The selected app must be actively outputting audio, and the correct process tree must be selected. Protected/sandboxed apps or Windows configurations may not produce capturable audio. Verify the app is not session-muted. The optional dedicated-output mute changes that endpoint’s mute state; no app routing is changed automatically.

## Development

`native/capture.cpp` is a standalone process-loopback producer; `mod/BDC_ZIC/Scripts/main.lua` is the Unreal-side consumer and `mod/BDC_ZIC/panel/panel.py` is the Tk controller. The fixed eight-slot file buffer bounds disk use but intentionally favors freshness over lossless delivery. `tests/mod_smoke.lua` mocks the UE4SS API and can be run with Lua 5.4 from the repository root; it is not an integration test. Do not interpret successful compilation or the smoke test as proof that the game integration works.
