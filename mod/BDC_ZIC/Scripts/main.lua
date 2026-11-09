-- Experimental local-only procedural sound emitter. No offsets or code patches.
local here = debug.getinfo(1, 'S').source:gsub('^@', ''):gsub('\\', '/'):match('^(.*)/[^/]+$')
local stream = here .. '/../stream/'
local active, queued, wave, component, slot = false, false, nil, nil, 0
local session = nil
local function log(s) print('[BDC-ZIC] ' .. tostring(s) .. '\n') end
local function valid(o)
    local ok, result = pcall(function() return o ~= nil and o:IsValid() end)
    return ok and result == true
end
local function clear()
    if valid(component) then pcall(function() component:Stop() end) end
    component, wave = nil, nil
end
local function start()
    clear()
    local engines = FindAllOf('GameEngine') or {}
    local world
    for _, e in ipairs(engines) do
        if valid(e) and not e:GetFullName():find('Default__', 1, true) then
            local ok, w = pcall(function() return e.GameViewport.World end)
            if ok and valid(w) then world = w; break end
        end
    end
    assert(valid(world), 'No world. Enter a match first.')
    local statics = StaticFindObject('/Script/Engine.Default__GameplayStatics')
    local factory = StaticFindObject('/Script/SteamCorePro.Default__SteamCoreProVoice')
    assert(valid(statics) and valid(factory), 'SteamCoreProVoice/GameplayStatics unavailable in this game build.')
    local pc = statics:GetPlayerController(world, 0)
    assert(valid(pc), 'Local player controller unavailable.')
    local pawn = pc:K2_GetPawn()
    assert(valid(pawn) and valid(pawn.RootComponent), 'Local pawn not ready.')
    wave = factory:ConstructSteamCoreProVoice(48000)
    assert(valid(wave), 'Could not construct procedural voice.')
    -- LocationType=KeepRelativeOffset. This is a normal attached 3D audio component,
    -- not a UI/2D sound; the game's mix/submix/reverb policy still applies.
    component = statics:SpawnSoundAttached(wave, pawn.RootComponent, FName('None'),
        {X=100.0,Y=0.0,Z=0.0}, {Pitch=0.0,Yaw=0.0,Roll=0.0}, 0,
        true, 1.0, 1.0, 0.0, nil, nil, false)
    assert(valid(component), 'SpawnSoundAttached failed.')
    slot = 0
    log('Emitter attached to local pawn. Start capture in the panel.')
end
local function tick()
    if not active then return end
    if not valid(component) or not valid(wave) then active = false; clear(); log('Emitter lost (map change?). Press F7 in a match to restart.'); return end
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
            wave:AddAudioBuffer(bytes)
        end
    end
end
RegisterKeyBind(Key.F7, function()
    ExecuteInGameThread(function()
        if active then active = false; clear(); log('Emitter stopped.'); return end
        local ok, err = pcall(start)
        if ok then active = true else active = false; clear(); log('Cannot start: ' .. tostring(err)) end
    end)
end)
LoopAsync(50, function()
    if active and not queued then
        queued = true
        ExecuteInGameThread(function()
            local ok, err = pcall(tick); queued = false
            if not ok then active = false; clear(); log('Playback failed: ' .. tostring(err)) end
        end)
    end
    return false
end)
ModRef.OnUnload = function() active = false; clear() end
log('Loaded. In a match press F7 to toggle the local emitter.')
