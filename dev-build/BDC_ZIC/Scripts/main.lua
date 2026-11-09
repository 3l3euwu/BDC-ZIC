-- Experimental local-only procedural sound emitter. No offsets or code patches.
local here = debug.getinfo(1, 'S').source:gsub('^@', ''):gsub('\\', '/'):match('^(.*)/[^/]+$')
local localappdata = os.getenv('LOCALAPPDATA')
local stream = localappdata and (localappdata:gsub('\\', '/') .. '/BDC-ZIC/stream/') or (here .. '/../stream/')
local active, queued, wave, component, slot = false, false, nil, nil, 0
local enabled, map_loading, retry_ticks = true, false, 0
local engine, attached_world, attached_pawn, last_error
local session = nil
local buffer_logged = false
local room = dofile(here .. '/room.lua')
local room_ticks, room_last_error, room_probe_logged = 0, nil, false
local playback_wait = 0
os.remove(stream .. 'room.txt')
local function log(s) print('[BDC-ZIC] ' .. tostring(s) .. '\n') end
local function valid(o)
    local ok, result = pcall(function() return o ~= nil and o:IsValid() end)
    return ok and result == true
end
local function clear(stop_component)
    os.remove(stream .. 'room.txt') -- never reuse an estimate after a world change
    -- Only call Stop on an explicit user request, never while objects may be tearing down.
    if stop_component and valid(component) then pcall(function() component:Stop() end) end
    component, wave, attached_world, attached_pawn = nil, nil, nil, nil
    playback_wait = 0
end
-- Cache the engine; repeated global object scans during map loading are unsafe.
local function context()
    if not valid(engine) then
        engine = nil
        for _, e in ipairs(FindAllOf('GameEngine') or {}) do
            if valid(e) and not e:GetFullName():find('Default__', 1, true) then engine = e; break end
        end
    end
    local world
    if valid(engine) then
        local ok, w = pcall(function() return engine.GameViewport.World end)
        if ok then world = w end
    end
    assert(valid(world), 'No world. Enter a match first.')
    local statics = StaticFindObject('/Script/Engine.Default__GameplayStatics')
    assert(valid(statics), 'GameplayStatics unavailable.')
    local pc = statics:GetPlayerController(world, 0)
    assert(valid(pc), 'Local player controller unavailable.')
    local pawn = pc:K2_GetPawn()
    assert(valid(pawn) and valid(pawn.RootComponent), 'Local pawn not ready.')
    return world, pawn, statics
end
local function start(world, pawn, statics)
    clear()
    local factory = StaticFindObject('/Script/SteamCorePro.Default__SteamCoreProVoice')
    assert(valid(factory), 'SteamCoreProVoice unavailable in this game build.')
    log('Diagnostic: constructing procedural voice.')
    wave = factory:ConstructSteamCoreProVoice(48000)
    assert(valid(wave), 'Could not construct procedural voice.')
    -- LocationType=KeepRelativeOffset. This is a normal attached 3D audio component,
    -- not a UI/2D sound; the game's mix/submix/reverb policy still applies.
    log('Diagnostic: spawning attached audio component.')
    component = statics:SpawnSoundAttached(wave, pawn.RootComponent, FName('None'),
        {X=100.0,Y=0.0,Z=0.0}, {Pitch=0.0,Yaw=0.0,Roll=0.0}, 0,
        true, 1.0, 1.0, 0.0, nil, nil, false)
    assert(valid(component), 'SpawnSoundAttached failed.')
    attached_world, attached_pawn = world:GetAddress(), pawn:GetAddress()
    slot = 0
    buffer_logged = false
    playback_wait = 60 -- 60 game-thread iterations at 50ms, approximately 3 seconds
    log('Emitter attached to local pawn. Waiting about 3 seconds before playback; start capture in the panel.')
end
local function update_room(pawn)
    local marker = io.open(stream .. 'auto-room', 'rb')
    if not marker then return end
    marker:close()
    if not room_probe_logged then log('Diagnostic: starting Auto Room geometry traces.'); room_probe_logged = true end
    local ok, reverb, size, hits, span = pcall(function()
        local kismet = StaticFindObject('/Script/Engine.Default__KismetSystemLibrary')
        assert(valid(kismet), 'KismetSystemLibrary unavailable')
        return room.measure(kismet, pawn)
    end)
    if not ok then
        os.remove(stream .. 'room.txt')
        if tostring(reverb) ~= room_last_error then
            room_last_error = tostring(reverb)
            log('Auto room unavailable; using manual effects: ' .. room_last_error)
        end
        return
    end
    local file = io.open(stream .. 'room.txt', 'wb')
    if file then file:write(string.format('%d %d %d %d\n', reverb, size, hits, span)); file:close() end
    room_last_error = nil
end
local function tick()
    if not active then return end
    if not valid(component) or not valid(wave) then
        enabled = false; active = false; clear(false)
        log('Emitter lost. Playback paused for safety; after loading, press F7 to resume.')
        return
    end
    if playback_wait > 0 then
        playback_wait = playback_wait - 1
        return
    end
    local marker = io.open(stream .. "session", "rb")
    if marker then
        local current = marker:read("*a"); marker:close()
        if current ~= session then session = current; slot = 0 end
    end
    -- Bound work and backlog. Each file is a complete 50ms mono PCM packet.
    for _ = 1, 4 do
        local path = stream .. 'chunk' .. slot .. '.pcm'
        local f = io.open(path, 'rb')
        if not f then
            -- If a producer has wrapped/overwritten a slot, resume at the next available one.
            local found = false
            for _ = 1, 7 do
                slot = (slot + 1) % 8; path = stream .. 'chunk' .. slot .. '.pcm'
                f = io.open(path, 'rb'); if f then found = true; break end
            end
            if not found then slot = (slot + 1) % 8; break end
        end
        local data = f:read(4801); f:close(); os.remove(path)
        slot = (slot + 1) % 8
        if data and #data == 4800 then
            local bytes = {data:byte(1, #data)}
            if not buffer_logged then log('Diagnostic: submitting first PCM packet to UE4SS.') end
            wave:AddAudioBuffer(bytes)
            if not buffer_logged then buffer_logged = true; log('Diagnostic: first PCM packet submitted.') end
        end
    end
end
-- LoadMap hooks suspend audio work while Unreal tears down / creates worlds.
-- Older builds may lack one or both hooks; polling remains a best-effort fallback.
local hook_ok = type(RegisterLoadMapPreHook) == 'function' and type(RegisterLoadMapPostHook) == 'function'
if hook_ok then
    local ok = pcall(function()
        -- Register post first: if pre registration fails, we cannot get stuck
        -- permanently suspended with no post hook to release us.
        RegisterLoadMapPostHook(function()
            map_loading = false; retry_ticks = 0; last_error = nil
            log(enabled and 'Diagnostic: map load completed; waiting for player.' or 'Map load completed. Press F7 after entering the game to resume.')
        end)
        RegisterLoadMapPreHook(function()
            map_loading = true; room_ticks = 0
            if active then enabled = false end
            active = false
            log('Diagnostic: map load starting; dropping emitter references without calling Unreal.')
            clear(false)
            log('Diagnostic: map-load emitter references cleared.')
        end)
    end)
    if not ok then map_loading = false; log('Map hooks unavailable; using polling fallback.') end
else
    log('Map hooks unavailable; using polling fallback.')
end
RegisterKeyBind(Key.F7, function()
    ExecuteInGameThread(function()
        if map_loading then log('Wait until the map has loaded before pressing F7.'); return end
        enabled = not enabled; room_ticks = 0
        if not enabled then active = false; clear(true); log('Emitter disabled. Press F7 to enable it.')
        else retry_ticks = 0; last_error = nil; log('Emitter enabled; waiting for local player.') end
    end)
end)
LoopAsync(50, function()
    if enabled and not queued then
        queued = true
        ExecuteInGameThread(function()
            queued = false
            if not enabled or map_loading then return end
            retry_ticks = retry_ticks - 1
            if retry_ticks <= 0 then
                retry_ticks = 40 -- check once every ~2 seconds, on the game thread
                local ok, world, pawn, statics = pcall(context)
                if ok then
                    if active and (world:GetAddress() ~= attached_world or pawn:GetAddress() ~= attached_pawn) then
                        enabled = false; active = false; clear(false)
                        log('Player or world changed. Playback paused for safety; press F7 after loading to resume.')
                        return
                    end
                    if not active then
                        local started, err = pcall(start, world, pawn, statics)
                        if started then active = true; last_error = nil
                        else
                            enabled = false; clear(false)
                            last_error = tostring(err); log('Emitter start failed: ' .. last_error .. '. Press F7 to retry after loading.')
                        end
                    end
                else
                    if active then
                        enabled = false; active = false; clear(false)
                        log('World or player unavailable. Playback paused for safety; press F7 after loading to resume.')
                        return
                    end
                    -- Missing world/player is normal while entering or changing a lobby;
                    -- report each distinct error once so unexpected reflection errors are visible.
                    if tostring(world) ~= last_error then
                        last_error = tostring(world); log('Waiting for player: ' .. last_error)
                    end
                end
            end
            if active then
                room_ticks = room_ticks - 1
                if room_ticks <= 0 then
                    room_ticks = 10 -- about 500 ms
                    local marker = io.open(stream .. 'auto-room', 'rb')
                    if marker then
                        marker:close()
                        local found, world, pawn = pcall(context)
                        if found and world:GetAddress() == attached_world and pawn:GetAddress() == attached_pawn then
                            update_room(pawn)
                        else
                            enabled = false; active = false; clear(false)
                            log('Player or world unavailable during Auto Room. Playback paused; press F7 after loading.')
                            return
                        end
                    else
                        os.remove(stream .. 'room.txt')
                    end
                end
                local ok, err = pcall(tick)
                if not ok then
                    enabled = false; active = false; clear(false)
                    log('Playback failed: ' .. tostring(err) .. '. Press F7 to retry.')
                end
            end
        end)
    end
    return false
end)
-- Some UE4SS builds expose ModRef as userdata without an assignable OnUnload.
-- Treat this optional hook as best-effort rather than failing the entire mod at load.
local unload_ok = pcall(function()
    ModRef.OnUnload = function() enabled = false; active = false; clear() end
end)
if not unload_ok then log('This UE4SS build does not support the optional unload hook; stop with F7 before unloading.') end
log('Loaded. The emitter attaches when the player is detected; playback starts about 3 seconds later. Press F7 after a map change to resume.')
log('Auto Room is experimental and runs geometry traces only when enabled in the panel.')
