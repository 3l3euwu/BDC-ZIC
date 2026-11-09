-- Run from repository root with Lua 5.4; simulates UE4SS, not Unreal or Windows.
local path = 'mod/BDC_ZIC/stream/'
os.execute('mkdir -p ' .. path)
local function packet()
    local f = assert(io.open(path .. 'session', 'wb')); f:write('test'); f:close()
    f = assert(io.open(path .. 'chunk0.pcm', 'wb')); f:write(string.rep('\1\0', 2400)); f:close()
end
packet()
local marker = assert(io.open(path .. 'auto-room', 'wb')); marker:close()
local good = {IsValid = function() return true end, GetAddress = function() return 1 end}
local submitted, stopped, started, contexts = 0, 0, 0, 0
local emitter_valid = true
local wave = setmetatable({AddAudioBuffer = function(_, bytes)
    assert(#bytes == 4800 and bytes[1] == 1 and bytes[2] == 0); submitted = submitted + 1
end}, {__index = good})
local component = setmetatable({IsValid = function() return emitter_valid end, Stop = function() stopped = stopped + 1 end}, {__index = good})
local location = function() return {X=0,Y=0,Z=0} end
local pawn1 = setmetatable({RootComponent = good, K2_GetActorLocation = location, GetAddress = function() return 10 end}, {__index = good})
local pawn2 = setmetatable({RootComponent = good, K2_GetActorLocation = location, GetAddress = function() return 20 end}, {__index = good})
local pawn = pawn1
local pc = setmetatable({K2_GetPawn = function() return pawn end}, {__index = good})
local statics = setmetatable({GetPlayerController = function() contexts = contexts + 1; return pc end, SpawnSoundAttached = function(_, sound) assert(sound == wave); started = started + 1; return component end}, {__index = good})
local factory = setmetatable({ConstructSteamCoreProVoice = function(_, rate) assert(rate == 48000); return wave end}, {__index = good})
local engine = setmetatable({GetFullName = function() return 'GameEngine' end, GameViewport = {World = good}}, {__index = good})
function FindAllOf() return {engine} end
local room_distance, traces = 600, 0
local kismet = setmetatable({LineTraceSingle = function(_, _, _, _, _, _, _, _, hit) traces = traces + 1; hit.Distance = room_distance; return true end}, {__index = good})
function StaticFindObject(name) if name:find('GameplayStatics') then return statics elseif name:find('KismetSystemLibrary') then return kismet else return factory end end
function FName(s) return s end
function ExecuteInGameThread(fn) fn() end
local key, loop, map_pre, map_post
Key = {F7=1}
ModRef = setmetatable({}, {__newindex = function() error('attempt to index a ModRef value') end})
function RegisterKeyBind(_, fn) key = fn end
function LoopAsync(_, fn) loop = fn end
function RegisterLoadMapPreHook(fn) map_pre = fn end
function RegisterLoadMapPostHook(fn) map_post = fn end
local real_time, ticks = os.time, 0
os.time = function() return math.floor(1000 + ticks / 20) end
assert(loadfile('mod/BDC_ZIC/Scripts/main.lua'))()
local function advance(count)
    for _ = 1, count do ticks = ticks + 1; loop() end
end
loop(); assert(started == 0)
advance(120); assert(started == 0) -- wait at least eight seconds
advance(50); assert(started == 1 and submitted == 1)
assert(traces >= 5)
local sample = assert(io.open(path .. 'room.txt', 'rb')); assert(sample:read('*a') == '4 6 5 1200\n'); sample:close()
room_distance = 200
advance(10)
sample = assert(io.open(path .. 'room.txt', 'rb')); assert(sample:read('*a') == '0 2 5 400\n'); sample:close()
map_pre(); assert(stopped == 0 and not io.open(path .. 'room.txt', 'rb'))
local old_traces = traces
advance(200); assert(started == 1 and traces == old_traces)
pawn = pawn2; packet(); map_post()
local before = contexts
advance(200); assert(started == 1 and contexts == before)
key(); loop(); assert(started == 1)
advance(170); assert(started == 2 and submitted == 2)
emitter_valid = false
loop(); assert(stopped == 0)
before = contexts
advance(100); assert(started == 2 and contexts == before)
emitter_valid = true; pawn = pawn1
key(); loop(); advance(170); assert(started == 3)
key(); assert(stopped == 1)
advance(100); assert(started == 3)
key(); loop(); advance(80); pawn = pawn2 -- reset delay if player changes before startup
advance(85); assert(started == 3)
advance(140); assert(started == 4)
os.time = real_time
os.remove(path .. 'session'); os.remove(path .. 'chunk0.pcm'); os.remove(path .. 'auto-room'); os.remove(path .. 'room.txt')
print('mod smoke test passed')
