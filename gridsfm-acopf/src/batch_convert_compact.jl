#!/usr/bin/env julia
using PowerModels, JSON3, OrderedCollections
PowerModels.silence()
include(joinpath(@__DIR__, "convert_lib.jl"))

listfile, out_dir = ARGS[1], ARGS[2]
mkpath(out_dir)
pyglist = joinpath(out_dir, "pyg.csv")
open(pyglist, "w") do io end
for line in readlines(listfile)
    isempty(strip(line)) && continue
    sid, cpath = split(strip(line), ','; limit=2)
    out = joinpath(out_dir, String(sid) * ".pyg.json")
    if isfile(out)
        open(pyglist, "a") do io; println(io, "$sid,$out"); end
        continue
    end
    println("CONV $sid")
    data = PowerModels.parse_file(String(cpath); import_all=false, validate=true)
    force_angle_limits!(data)
    opf = build_grid_only(data)
    open(out, "w") do io; JSON3.write(io, opf); end
    open(pyglist, "a") do io; println(io, "$sid,$out"); end
end
println("BATCH CONV DONE")
