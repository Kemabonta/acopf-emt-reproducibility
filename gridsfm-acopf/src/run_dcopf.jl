#!/usr/bin/env julia
# DC-OPF reference line: PowerModels DCPPowerModel, same harmonized data (+/-60 deg, rate A).
# Usage: julia --project=... run_dcopf.jl list.csv out_dir
using PowerModels, Ipopt, JuMP, JSON3
PowerModels.silence()
function force_limits!(data)
    for (_,b) in data["branch"]; b["angmin"] = -π/3; b["angmax"] = π/3; end
end
listfile, out_dir = ARGS[1], ARGS[2]; mkpath(out_dir)
solver = optimizer_with_attributes(Ipopt.Optimizer, "print_level"=>0, "tol"=>1e-8, "constr_viol_tol"=>1e-8, "max_iter"=>3000)
for line in readlines(listfile)
    isempty(strip(line)) && continue
    sid, cpath = split(strip(line), ','; limit=2)
    outp = joinpath(out_dir, String(sid) * ".json"); isfile(outp) && continue
    try
        data = PowerModels.parse_file(String(cpath); import_all=false, validate=true); force_limits!(data)
        t0 = time(); result = solve_opf(data, DCPPowerModel, solver); wall = time() - t0
        sol = get(result, "solution", Dict()); st = string(result["termination_status"])
        out = Dict("tool"=>"PowerModels DC-OPF", "scenario_id"=>String(sid), "termination_status"=>st,
            "solved"=>st in ("LOCALLY_SOLVED","OPTIMAL","ALMOST_LOCALLY_SOLVED"),
            "objective"=>Float64(get(result, "objective", NaN)), "solve_time"=>Float64(get(result, "solve_time", NaN)), "wall_time"=>wall,
            "baseMVA"=>data["baseMVA"],
            "bus"=>Dict(k => Dict("vm"=>1.0, "va"=>b["va"]) for (k,b) in get(sol, "bus", Dict())),
            "gen"=>Dict(k => Dict("pg"=>g["pg"], "qg"=>0.0) for (k,g) in get(sol, "gen", Dict())))
        open(outp, "w") do io; JSON3.write(io, out); end
        println("DC $sid $st $(round(wall; digits=3))")
    catch e
        open(outp, "w") do io; JSON3.write(io, Dict("scenario_id"=>String(sid), "solved"=>false, "termination_status"=>"ERROR", "error"=>string(e), "objective"=>nothing)); end
        println("DC $sid ERROR $e")
    end
end
println("DC DONE")
