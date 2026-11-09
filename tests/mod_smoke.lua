-- Run from repository root with Lua 5.4; simulates UE4SS, not Unreal or Windows.
local path = 'mod/BDC_ZIC/stream/'
os.execute('mkdir -p ' .. path)
local f = assert(io.open(path .. 'session', 'wb')); f:write('test'); f:close()
f = assert(io.open(path .. 'chunk0.pcm', 'wb')); f:write(string.rep('\1\0', 2400)); f:close()
local good = {IsValid = function() return true end}
local submitted, stopped = 0, false
local wave = setmetatable({AddAudioBuffer = function(_, bytes)
    assert(#bytes == 4800 and bytes[1] == 1 and bytes[2] == 0); submitted = submitted + 1
end}, {__index = good})
local component = setmetatable({Stop = function() stopped = true end}, {__index = good})
local pawn = setmetatable({RootComponent = good}, {__index = good})
local pc = setmetatable({K2_GetPawn = function() return pawn end}, {__index = good})
local statics = setmetatable({GetPlayerController = function() return pc end, SpawnSoundAttached = function(_, sound) assert(sound == wave); return component end}, {__index = good})
local factory = setmetatable({ConstructSteamCoreProVoice = function(_, rate) assert(rate == 48000); return wave end}, {__index = good})
local engine = setmetatable({GetFullName = function() return 'GameEngine' end, GameViewport = {World = good}}, {__index = good})
function FindAllOf() return {engine} end
function StaticFindObject(name) if name:find('GameplayStatics') then return statics else return factory end end
function FName(s) return s end
function ExecuteInGameThread(fn) fn() end
local key, loop
Key = {F7=1}; ModRef = {}
function RegisterKeyBind(_, fn) key = fn end
function LoopAsync(_, fn) loop = fn end
assert(loadfile('mod/BDC_ZIC/Scripts/main.lua'))()
key(); loop(); assert(submitted == 1); key(); assert(stopped)
os.remove(path .. 'session'); os.remove(path .. 'chunk0.pcm')
print('mod smoke test passed')
