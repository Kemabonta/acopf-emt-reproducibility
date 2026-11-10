#!/usr/bin/env julia
# Usage: julia run_powermodels_warm.jl list.csv out_dir warm.json [timeout_s=120]
using PowerModels, Ipopt, JuMP, JSON3
PowerModels.silence()
const TIMEOUT = length(ARGS) >= 4 ? parse(Float64, ARGS[4]) : 120.0

function force_limits!(data)
    for (_,b) in data["branch"]; b["angmin"]=-π/3; b["angmax"]=π/3; end
end

function apply_warm!(data, warm)
    if warm === nothing; return; end
    if haskey(warm, "bus")
        for (k,v) in warm["bus"]
            ks=string(k)
            haskey(data["bus"], ks) || continue
            data["bus"][ks]["vm"] = Float64(v["vm"])
            if haskey(v, "va"); data["bus"][ks]["va"]=Float64(v["va"])
            elseif haskey(v, "va_deg"); data["bus"][ks]["va"]=Float64(v["va_deg"])*π/180; end
        end
    end
    if haskey(warm, "gen")
        for (k,v) in warm["gen"]
            ks=string(k)
            haskey(data["gen"], ks) || continue
            if haskey(v, "pg"); data["gen"][ks]["pg"]=Float64(v["pg"])
            elseif haskey(v, "pg_mw"); data["gen"][ks]["pg"]=Float64(v["pg_mw"])/data["baseMVA"]; end
            if haskey(v, "qg"); data["gen"][ks]["qg"]=Float64(v["qg"])
            elseif haskey(v, "qg_mvar"); data["gen"][ks]["qg"]=Float64(v["qg_mvar"])/data["baseMVA"]; end
        end
    end
end

function solve_one(path; warm=nothing, do_warm::Bool=false)
    data = PowerModels.parse_file(path; import_all=false, validate=true)
    force_limits!(data)
    apply_warm!(data, warm)
    # Sane options: seed starting point via data fields; avoid aggressive warm_start_init_point
    # which hung previously. Use moderate bound push.
    attrs = Dict{String,Any}(
        "print_level"=>0, "max_iter"=>3000, "tol"=>1e-8, "constr_viol_tol"=>1e-8,
        "max_cpu_time"=>TIMEOUT,
    )
    if do_warm
        attrs["warm_start_init_point"] = "yes"
        attrs["mu_init"] = 1e-1
        attrs["warm_start_bound_push"] = 1e-3
        attrs["warm_start_bound_frac"] = 1e-3
        attrs["warm_start_slack_bound_push"] = 1e-3
        attrs["warm_start_slack_bound_frac"] = 1e-3
        attrs["warm_start_mult_bound_push"] = 1e-3
    end
    solver = optimizer_with_attributes(Ipopt.Optimizer, attrs...)
    t0 = time()
    result = solve_ac_opf(data, solver)
    wall = time() - t0
    timed_out = wall >= TIMEOUT - 0.5 || occursin("Maximum", string(result["termination_status"])) ||
                string(result["termination_status"]) == "TIME_LIMIT" ||
                occursin("TIME", uppercase(string(get(result,"termination_status",""))))
    sol = result["solution"]
    return Dict(
        "tool" => do_warm ? "PowerModels+Ipopt(warm_GridSFM)" : "PowerModels+Ipopt(cold)",
        "case" => path,
        "termination_status" => string(result["termination_status"]),
        "solved" => string(result["termination_status"]) in ("LOCALLY_SOLVED","OPTIMAL","ALMOST_LOCALLY_SOLVED"),
        "timed_out" => timed_out || wall >= TIMEOUT,
        "objective" => Float64(get(result, "objective", NaN)),
        "solve_time" => Float64(get(result, "solve_time", NaN)),
        "wall_time" => wall,
        "timeout_s" => TIMEOUT,
        "baseMVA" => data["baseMVA"],
        "bus" => Dict(k => Dict("vm"=>b["vm"], "va"=>b["va"]) for (k,b) in sol["bus"]),
        "gen" => Dict(k => Dict("pg"=>g["pg"], "qg"=>g["qg"]) for (k,g) in sol["gen"]),
    )
end

function main()
    listfile, out_dir, warm_path = ARGS[1], ARGS[2], ARGS[3]
    mkpath(out_dir)
    warm_all = JSON3.read(read(warm_path, String))
    for line in readlines(listfile)
        isempty(strip(line)) && continue
        startswith(strip(line), "#") && continue
        sid, cpath = split(strip(line), ','; limit=2)
        outp = joinpath(out_dir, String(sid)*".json")
        isfile(outp) && continue
        println("WARM $sid")
        warm = nothing
        if haskey(warm_all, Symbol(sid)); warm = warm_all[Symbol(sid)]
        elseif haskey(warm_all, sid); warm = warm_all[sid]; end
        try
            out = solve_one(String(cpath); warm=warm, do_warm=true)
            out["scenario_id"] = String(sid)
            open(outp, "w") do io; JSON3.write(io, out); end
            println("  status=$(out["termination_status"]) t=$(out["solve_time"]) timed_out=$(out["timed_out"])")
        catch e
            open(outp, "w") do io
                JSON3.write(io, Dict("scenario_id"=>String(sid), "solved"=>false, "timed_out"=>true,
                    "termination_status"=>"ERROR", "error"=>string(e), "objective"=>NaN,
                    "solve_time"=>NaN, "wall_time"=>NaN, "tool"=>"PowerModels+Ipopt(warm_GridSFM)"))
            end
            @show e
        end
    end
end
main()
