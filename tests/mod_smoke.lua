-- Run from repository root with Lua 5.4; simulates UE4SS, not Unreal or Windows.
local path = 'mod/BDC_ZIC/stream/'
os.execute('mkdir -p ' .. path)
local function packet()
    local f = assert(io.open(path .. 'session', 'wb')); f:write('test'); f:close()
    f = assert(io.open(path .. 'chunk0.pcm', 'wb')); f:write(string.rep('\1\0', 2400)); f:close()
end
packet()
local good = {IsValid = function() return true end, GetAddress = function() return 1 end}
local submitted, stopped, started = 0, 0, 0
local wave = setmetatable({AddAudioBuffer = function(_, bytes)
    assert(#bytes == 4800 and bytes[1] == 1 and bytes[2] == 0); submitted = submitted + 1
end}, {__index = good})
local component = setmetatable({Stop = function() stopped = stopped + 1 end}, {__index = good})
local pawn1 = setmetatable({RootComponent = good, GetAddress = function() return 10 end}, {__index = good})
local pawn2 = setmetatable({RootComponent = good, GetAddress = function() return 20 end}, {__index = good})
local pawn = pawn1
local pc = setmetatable({K2_GetPawn = function() return pawn end}, {__index = good})
local statics = setmetatable({GetPlayerController = function() return pc end, SpawnSoundAttached = function(_, sound) assert(sound == wave); started = started + 1; return component end}, {__index = good})
local factory = setmetatable({ConstructSteamCoreProVoice = function(_, rate) assert(rate == 48000); return wave end}, {__index = good})
local engine = setmetatable({GetFullName = function() return 'GameEngine' end, GameViewport = {World = good}}, {__index = good})
function FindAllOf() return {engine} end
function StaticFindObject(name) if name:find('GameplayStatics') then return statics else return factory end end
function FName(s) return s end
function ExecuteInGameThread(fn) fn() end
local key, loop, map_pre, map_post
Key = {F7=1}
ModRef = setmetatable({}, {__newindex = function() error('attempt to index a ModRef value') end})
function RegisterKeyBind(_, fn) key = fn end
function LoopAsync(_, fn) loop = fn end
function RegisterLoadMapPreHook(fn) map_pre = fn end
function RegisterLoadMapPostHook(fn) map_post = fn end
assert(loadfile('mod/BDC_ZIC/Scripts/main.lua'))()
loop(); assert(started == 1 and submitted == 1) -- automatically starts
map_pre(); assert(stopped == 1)
for _ = 1, 45 do loop() end
assert(started == 1) -- never starts during load
pawn = pawn2; packet(); map_post(); loop()
assert(started == 2 and submitted == 2) -- reconnect after load without F7
pawn = pawn1
for _ = 1, 40 do loop() end
assert(started == 3 and stopped == 2) -- pawn change without a map load
key(); assert(stopped == 3)
for _ = 1, 50 do loop() end
assert(started == 3) -- F7 disables automatic restart
key(); loop(); assert(started == 4) -- F7 re-enables
os.remove(path .. 'session'); os.remove(path .. 'chunk0.pcm')
print('mod smoke test passed')
