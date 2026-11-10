#!/usr/bin/env julia
# Usage: julia --project=... run_powermodels.jl list.csv out_dir [warm.json]
# list.csv lines: scenario_id,case_path
using PowerModels, Ipopt, JuMP, JSON3
PowerModels.silence()

function force_limits!(data)
    for (_,b) in data["branch"]
        b["angmin"] = -π/3; b["angmax"] = π/3
    end
end

function solve_one(path; warm=nothing, warm_ipopt::Bool=false)
    data = PowerModels.parse_file(path; import_all=false, validate=true)
    force_limits!(data)
    if warm !== nothing
        if haskey(warm, "bus")
            for (k,v) in warm["bus"]
                ks = string(k)
                if haskey(data["bus"], ks)
                    data["bus"][ks]["vm"] = Float64(v["vm"])
                    # accept va radians or va_deg
                    if haskey(v, "va")
                        data["bus"][ks]["va"] = Float64(v["va"])
                    elseif haskey(v, "va_deg")
                        data["bus"][ks]["va"] = Float64(v["va_deg"]) * π / 180
                    end
                end
            end
        end
        if haskey(warm, "gen")
            for (k,v) in warm["gen"]
                ks = string(k)
                if haskey(data["gen"], ks)
                    # GridSFM pg is pu; PowerModels gen pg is also pu in data dict
                    pg = Float64(get(v, "pg", get(v, "pg_mw", 0.0) / data["baseMVA"]))
                    qg = Float64(get(v, "qg", get(v, "qg_mvar", 0.0) / data["baseMVA"]))
                    if haskey(v, "pg_mw") && !haskey(v, "pg")
                        pg = Float64(v["pg_mw"]) / data["baseMVA"]
                        qg = Float64(v["qg_mvar"]) / data["baseMVA"]
                    end
                    data["gen"][ks]["pg"] = pg
                    data["gen"][ks]["qg"] = qg
                end
            end
        end
    end
    attrs = Dict{String,Any}(
        "print_level"=>0, "max_iter"=>3000, "tol"=>1e-8, "constr_viol_tol"=>1e-8,
    )
    if warm_ipopt
        attrs["warm_start_init_point"] = "yes"
        attrs["mu_init"] = 1.0
        attrs["warm_start_bound_push"] = 1.0
        attrs["warm_start_bound_frac"] = 1e-16
        attrs["warm_start_slack_bound_frac"] = 1e-16
        attrs["warm_start_slack_bound_push"] = 1e-16
        attrs["warm_start_mult_bound_push"] = 1e-16
    end
    solver = optimizer_with_attributes(Ipopt.Optimizer, attrs...)
    t0 = time()
    result = solve_ac_opf(data, solver)
    wall = time() - t0
    sol = result["solution"]
    return Dict(
        "tool" => warm_ipopt ? "PowerModels+Ipopt(warm_GridSFM)" : "PowerModels+Ipopt",
        "case" => path,
        "termination_status" => string(result["termination_status"]),
        "solved" => string(result["termination_status"]) in ("LOCALLY_SOLVED","OPTIMAL","ALMOST_LOCALLY_SOLVED"),
        "objective" => Float64(get(result, "objective", NaN)),
        "solve_time" => Float64(get(result, "solve_time", NaN)),
        "wall_time" => wall,
        "baseMVA" => data["baseMVA"],
        "bus" => Dict(k => Dict("vm"=>b["vm"], "va"=>b["va"]) for (k,b) in sol["bus"]),
        "gen" => Dict(k => Dict("pg"=>g["pg"], "qg"=>g["qg"]) for (k,g) in sol["gen"]),
    )
end

function main()
    listfile = ARGS[1]; out_dir = ARGS[2]
    mkpath(out_dir)
    warm_all = nothing
    warm_ipopt = false
    if length(ARGS) >= 3
        warm_all = JSON3.read(read(ARGS[3], String))
        warm_ipopt = true
    end
    for line in readlines(listfile)
        isempty(strip(line)) && continue
        startswith(strip(line), "#") && continue
        sid, cpath = split(strip(line), ','; limit=2)
        outp = joinpath(out_dir, String(sid) * ".json")
        if isfile(outp)
            println("PM $sid skip")
            continue
        end
        println("PM $sid")
        warm = nothing
        if warm_all !== nothing
            # JSON3 Object
            if haskey(warm_all, Symbol(sid))
                warm = warm_all[Symbol(sid)]
            elseif haskey(warm_all, sid)
                warm = warm_all[sid]
            end
        end
        try
            out = solve_one(String(cpath); warm=warm, warm_ipopt=warm_ipopt)
            out["scenario_id"] = String(sid)
            open(joinpath(out_dir, String(sid) * ".json"), "w") do io
                JSON3.write(io, out)
            end
            println("  status=$(out["termination_status"]) obj=$(out["objective"]) t=$(out["solve_time"])")
        catch e
            open(joinpath(out_dir, String(sid) * ".json"), "w") do io
                JSON3.write(io, Dict("scenario_id"=>String(sid), "solved"=>false,
                    "termination_status"=>"ERROR", "error"=>string(e),
                    "objective"=>NaN, "solve_time"=>NaN, "wall_time"=>NaN,
                    "tool"=>"PowerModels+Ipopt"))
            end
            @show e
        end
    end
end
main()
