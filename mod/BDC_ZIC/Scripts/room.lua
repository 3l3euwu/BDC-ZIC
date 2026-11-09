-- Experimental collision-based room estimate. Not Bodycam's acoustic metadata.
local M = {}
local range = 2000 -- cm; 20 metres per direction
local directions = {{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1}}
local color = {R=0,G=0,B=0,A=0}
function M.measure(kismet, pawn)
    local loc = pawn:K2_GetActorLocation()
    local x,y,z = tonumber(loc.X), tonumber(loc.Y), tonumber(loc.Z)
    assert(x and y and z, 'player location unavailable')
    local start = {X=x,Y=y,Z=z+70}
    local hits, horizontal_hits, horizontal_total, roof = 0, 0, 0, false
    for i, d in ipairs(directions) do
        local hit = {}
        local target = {X=x+d[1]*range,Y=y+d[2]*range,Z=z+70+d[3]*range}
        local found = kismet:LineTraceSingle(pawn, start, target, 0, false, {pawn}, 0,
                                             hit, true, color, color, 0.0)
        local distance = range
        if found then
            distance = tonumber(hit.Distance)
            assert(distance and distance == distance and distance >= 0 and distance <= range + 1,
                   'trace hit distance unavailable')
            hits = hits + 1
            if i == 5 then roof = true else horizontal_hits = horizontal_hits + 1 end
        end
        if i <= 4 then horizontal_total = horizontal_total + distance end
    end
    -- Require a ceiling and at least two walls. Otherwise treat the area as open.
    if not roof or horizontal_hits < 2 then return 0, 0, hits, 0 end
    -- Opposite ray pairs approximate width and depth. Misses cap each ray at 20m.
    -- Average pair span in cm: for a rectangular room this is (width + depth)/2.
    local span_cm = math.min(4000, math.floor(horizontal_total / 2 + 0.5))
    local size = math.max(1, math.min(10, math.floor(span_cm / 200 + 0.5)))
    -- Up to ~4m span is dry; larger spaces progressively increase reverb to 10.
    local reverb = math.max(0, math.min(10, math.floor((span_cm - 400) / 180 + 0.5)))
    return reverb, size, hits, span_cm
end
return M
