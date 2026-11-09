-- Experimental geometry estimate, not the game's gunshot / reverb parameters.
local M = {}
local range = 2000 -- 20m in Unreal centimetres
local directions = {{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1}}
local color = {R=0,G=0,B=0,A=0}
function M.measure(kismet, pawn)
    local loc = pawn:K2_GetActorLocation()
    local x,y,z = tonumber(loc.X), tonumber(loc.Y), tonumber(loc.Z)
    assert(x and y and z, 'player location unavailable')
    local start = {X=x,Y=y,Z=z+70}
    local hits, total = 0, 0
    for _, d in ipairs(directions) do
        local hit = {}
        local target = {X=x+d[1]*range,Y=y+d[2]*range,Z=z+70+d[3]*range}
        local found = kismet:LineTraceSingle(pawn, start, target, 0, false, {pawn}, 0,
                                             hit, true, color, color, 0.0)
        if found then
            local distance = tonumber(hit.Distance)
            assert(distance and distance == distance and distance >= 0 and distance <= range + 1,
                   'trace hit distance unavailable')
            hits, total = hits + 1, total + distance
        end
    end
    -- Open spaces are dry. More surrounding surfaces add synthetic reverb;
    -- mean hit distance selects an approximate room size, never real geometry volume.
    if hits == 0 then return 0, 0, 0 end
    local size = math.max(1, math.min(10, math.floor((total / hits) / 200 + 0.5)))
    local reverb = math.max(1, math.min(10, hits * 2))
    return reverb, size, hits
end
return M
