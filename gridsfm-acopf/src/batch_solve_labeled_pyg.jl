#!/usr/bin/env julia
# Solve MATPOWER cases and write labeled .pyg.json (for FT).
# Usage: julia --project=... batch_solve_labeled_pyg.jl list.csv out_dir
using PowerModels, Ipopt, JuMP, JSON3, OrderedCollections
PowerModels.silence()
include(joinpath(@__DIR__, "convert_lib.jl"))

# Pull official build_gridsfm_data for duals+solution
const EXPORT_JL = joinpath(@__DIR__, "..", "repos", "gridsfm", "power_grid", "US",
                           "topology_solver_pipeline", "export_gridsfm_data.jl")

listfile, out_dir = ARGS[1], ARGS[2]
mkpath(out_dir)
# include export helpers without running its main — load by reading functions
# Simpler path: solve then use build_grid_only and fill solution from result.
include_export = isfile(EXPORT_JL)
if include_export
    # export_gridsfm_data.jl calls main at end if PROGRAM_FILE matches — set differently
    # Just redefine build using our solution fill.
end

function fill_solution!(opf, data, result)
    r = get(result, "solution", Dict())
    ts = string(get(result, "termination_status", "UNKNOWN"))
    feas = any(s -> occursin(s, uppercase(ts)),
               ["LOCALLY_SOLVED","OPTIMAL","ALMOST_LOCALLY_SOLVED"])
    bids = opf["metadata"]["bus_id_map"]
    gids = opf["metadata"]["gen_id_map"]
    sb = Vector{Vector{Float64}}()
    for bid in bids
        b = get(get(r, "bus", Dict()), string(bid), nothing)
        if b === nothing
            push!(sb, [0.0, 1.0])
        else
            push!(sb, Float64[b["va"], b["vm"]])
        end
    end
    sg = Vector{Vector{Float64}}()
    for gid in gids
        g = get(get(r, "gen", Dict()), string(gid), nothing)
        if g === nothing
            push!(sg, [0.0, 0.0])
        else
            push!(sg, Float64[g["pg"], g["qg"]])
        end
    end
    opf["solution"]["nodes"]["bus"] = sb
    opf["solution"]["nodes"]["generator"] = sg
    opf["metadata"]["objective"] = get(result, "objective", nothing)
    opf["metadata"]["termination_status"] = ts
    opf["metadata"]["feasible"] = feas
    return feas
end

for line in readlines(listfile)
    isempty(strip(line)) && continue
    sid, cpath = split(strip(line), ','; limit=2)
    out = joinpath(out_dir, String(sid) * ".pyg.json")
    isfile(out) && continue
    println("SOLVE+LABEL $sid")
    try
        data = PowerModels.parse_file(String(cpath); import_all=false, validate=true)
        force_angle_limits!(data)
        n_bus = length(data["bus"])
        max_iter = n_bus > 1000 ? 5000 : 3000
        solver = optimizer_with_attributes(Ipopt.Optimizer,
            "print_level"=>0, "max_iter"=>max_iter, "tol"=>1e-8, "constr_viol_tol"=>1e-8,
            "max_cpu_time"=>120.0)
        t0 = time()
        result = solve_ac_opf(data, solver)
        println("  status=$(result["termination_status"]) obj=$(get(result,"objective",NaN)) t=$(round(time()-t0;digits=2))")
        opf = build_grid_only(data)
        fill_solution!(opf, data, result)
        open(out, "w") do io; JSON3.pretty(io, opf); end
    catch e
        println("  ERROR $e")
        open(out * ".err", "w") do io; println(io, e); end
    end
end
println("LABELED BATCH DONE")
