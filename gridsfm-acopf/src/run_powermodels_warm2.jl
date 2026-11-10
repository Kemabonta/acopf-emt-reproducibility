#!/usr/bin/env julia
# Warm-start runner v2 (fix): seeds PowerModels through the *_start keys it actually reads
# (vm_start, va_start, pg_start, qg_start). v1 wrote vm/va/pg/qg, which ACPPowerModel ignores as starts.
# Usage: julia run_powermodels_warm2.jl list.csv out_dir seeds.json timeout_s mode
#   mode A: IPOPT options identical to the bulk cold runs (tol 1e-8) + primal start
#   mode B: warm_start_init_point=yes, mu_init=1.0, warm_start_bound_push=1.0
# Scenarios absent from seeds.json run cold with the same options (paired control).
using PowerModels, Ipopt, JuMP, JSON3
PowerModels.silence()
listfile, out_dir, seed_path = ARGS[1], ARGS[2], ARGS[3]
TIMEOUT = parse(Float64, ARGS[4]); MODE = ARGS[5]
mkpath(out_dir)
seeds = JSON3.read(read(seed_path, String))
fin(x) = (x isa Real && isfinite(x)) ? Float64(x) : nothing  # JSON3 cannot write NaN (same fix as run_dcopf.jl)
function force_limits!(data); for (_,b) in data["branch"]; b["angmin"]=-π/3; b["angmax"]=π/3; end; end
function apply_seed!(data, s)
    for (k,v) in s[:bus]; ks=string(k); haskey(data["bus"], ks) || continue
        data["bus"][ks]["vm_start"] = Float64(v[:vm]); data["bus"][ks]["va_start"] = Float64(v[:va]); end
    for (k,v) in s[:gen]; ks=string(k); haskey(data["gen"], ks) || continue
        data["gen"][ks]["pg_start"] = Float64(v[:pg]); data["gen"][ks]["qg_start"] = Float64(v[:qg]); end
end
attrs = Dict{String,Any}("print_level"=>0, "max_iter"=>3000, "tol"=>1e-8, "constr_viol_tol"=>1e-8, "max_cpu_time"=>TIMEOUT)
if MODE == "B"
    attrs["warm_start_init_point"]="yes"; attrs["mu_init"]=1.0; attrs["warm_start_bound_push"]=1.0
end
solver = optimizer_with_attributes(Ipopt.Optimizer, attrs...)
lines = [l for l in readlines(listfile) if !isempty(strip(l))]
# discarded JIT warm-up on the first case
let (sid, cpath) = split(strip(lines[1]), ','; limit=2)
    d = PowerModels.parse_file(String(cpath); import_all=false, validate=true); force_limits!(d); solve_ac_opf(d, solver)
end
for line in lines
    sid, cpath = split(strip(line), ','; limit=2); outp = joinpath(out_dir, String(sid)*".json"); isfile(outp) && continue
    data = PowerModels.parse_file(String(cpath); import_all=false, validate=true); force_limits!(data)
    seeded = haskey(seeds, Symbol(sid)); seeded && apply_seed!(data, seeds[Symbol(sid)])
    t0 = time()
    pm = instantiate_model(data, ACPPowerModel, PowerModels.build_opf)
    result = optimize_model!(pm, optimizer=solver)
    wall = time() - t0
    iters = try JuMP.barrier_iterations(pm.model) catch; -1 end
    st = string(result["termination_status"])
    out = Dict("scenario_id"=>String(sid), "mode"=>MODE, "seeded"=>seeded, "termination_status"=>st,
        "solved"=>st in ("LOCALLY_SOLVED","OPTIMAL","ALMOST_LOCALLY_SOLVED"), "timed_out"=>occursin("TIME", uppercase(st)),
        "objective"=>fin(get(result,"objective",NaN)), "solve_time"=>fin(get(result,"solve_time",NaN)),
        "wall_time"=>wall, "iterations"=>iters)
    open(outp, "w") do io; JSON3.write(io, out); end
    println("W $sid seeded=$seeded $st it=$iters t=$(something(out["solve_time"],NaN))")
end
println("WARM2 DONE")
