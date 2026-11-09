local room = dofile('mod/BDC_ZIC/Scripts/room.lua')
local position = {X=0,Y=0,Z=0}
local pawn = {K2_GetActorLocation = function() return position end}
local width, depth, roof = 400, 400, true
local tracer = {LineTraceSingle = function(_, world, start, target, channel, complex, ignored, debug, hit)
    assert(world == pawn and channel == 0 and ignored[1] == pawn)
    local distance
    if target.X > start.X then distance = width / 2 - position.X
    elseif target.X < start.X then distance = width / 2 + position.X
    elseif target.Y > start.Y then distance = depth / 2 - position.Y
    elseif target.Y < start.Y then distance = depth / 2 + position.Y
    elseif roof then distance = 250 end
    if distance and distance <= 2000 then hit.Distance = distance; return true end
    return false
end}
local reverb, size, hits, span = room.measure(tracer, pawn)
assert(reverb == 0 and size == 2 and hits == 5 and span == 400) -- 4m square, dry
width, depth = 1600, 1600
reverb, size, hits, span = room.measure(tracer, pawn)
assert(reverb == 7 and size == 8 and hits == 5 and span == 1600) -- 16m square
position.X = 700
local reverb2, _, _, span2 = room.measure(tracer, pawn)
assert(reverb2 == reverb and span2 == span) -- walking near a wall shouldn't change size
roof = false
reverb, size, hits, span = room.measure(tracer, pawn)
assert(reverb == 0 and size == 0 and span == 0) -- open sky is dry
local malformed = {LineTraceSingle = function() return true end}
assert(not pcall(room.measure, malformed, pawn))
print('room estimate test passed')
