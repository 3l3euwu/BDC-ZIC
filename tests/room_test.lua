local room = dofile('mod/BDC_ZIC/Scripts/room.lua')
local pawn = {K2_GetActorLocation = function() return {X=0,Y=0,Z=0} end}
local calls = 0
local empty = {LineTraceSingle = function(_, world, start, target, channel, complex, ignored, debug, hit)
    assert(world == pawn and channel == 0 and ignored[1] == pawn)
    calls = calls + 1; return false
end}
local reverb, size, hits = room.measure(empty, pawn)
assert(reverb == 0 and size == 0 and hits == 0 and calls == 5)
local indoors = {LineTraceSingle = function(_, _, _, _, _, _, _, _, hit)
    hit.Distance = 600; return true
end}
reverb, size, hits = room.measure(indoors, pawn)
assert(reverb == 10 and size == 3 and hits == 5)
local malformed = {LineTraceSingle = function() return true end}
assert(not pcall(room.measure, malformed, pawn))
print('room estimate test passed')
