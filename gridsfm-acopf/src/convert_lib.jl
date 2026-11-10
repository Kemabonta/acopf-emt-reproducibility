#!/usr/bin/env julia
# Convert MATPOWER .m (or PowerModels JSON) to GridSFM .pyg.json grid schema.
# Conversion assumptions are logged to stderr / a sidecar JSON.
#
# Usage:
#   julia --project=... mpc_to_pyg.jl input.m output.pyg.json [--solve]
#
# Assumptions (logged):
# 1. PowerModels.parse_file with import_all=false, validate=true
# 2. Branch angmin/angmax already set in file to +/-60 deg; we also force
#    +/- pi/3 rad after parse so PowerModels' 0/0 pad cannot diverge.
# 3. Offline gens (gen_status=0) excluded from generator node list (GridSFM schema).
# 4. Transformers vs AC lines via PowerModels tap/shift heuristic (_is_xfmr).
# 5. rate_b/rate_c fall back to rate_a when zero (GridSFM _rates).
# 6. Without --solve, solution tensors are zeros; metadata.objective=null.
# 7. Costs from polynomial gencost (MODEL=2) mapped to cp2,cp1,cp0 in $/pu-hr.

using PowerModels, Ipopt, JuMP, JSON3, OrderedCollections

PowerModels.silence()

function _gcost(g)
    # PowerModels stores cost as vector; quadratic $/hr on MW: c2*Pg^2+c1*Pg+c0
    # GridSFM expects cp on per-unit Pg (baseMVA). export_gridsfm_data scales?
    # Follow export_gridsfm_data.jl _gcost
    cost = get(g, "cost", Float64[])
    n = get(g, "ncost", length(cost))
    model = get(g, "model", 2)
    if model == 2 && n >= 3
        return (Float64(cost[1]), Float64(cost[2]), Float64(cost[3]))
    elseif model == 2 && n == 2
        return (0.0, Float64(cost[1]), Float64(cost[2]))
    elseif model == 2 && n == 1
        return (0.0, 0.0, Float64(cost[1]))
    else
        return (0.0, 0.0, 0.0)
    end
end

function _rates(b)
    ra = Float64(get(b, "rate_a", 0.0))
    rb = Float64(get(b, "rate_b", 0.0)); rb = rb == 0 ? ra : rb
    rc = Float64(get(b, "rate_c", 0.0)); rc = rc == 0 ? rb : rc
    return ra, rb, rc
end

function _is_xfmr(b)
    # Match export_gridsfm_data.jl: prefer PowerModels "transformer" flag
    # (set from MATPOWER ratio!=0), else tap/shift deviation from nominal.
    if haskey(b, "transformer")
        return Bool(b["transformer"])
    end
    tap = get(b, "tap", 1.0)
    shift = get(b, "shift", 0.0)
    return abs(tap - 1.0) > 1e-8 || abs(shift) > 1e-8
end

function build_grid_only(data)
    bv = sort([(parse(Int,k), b) for (k,b) in data["bus"]]; by=first)
    bf = [[b["base_kv"], b["bus_type"], b["vmin"], b["vmax"]] for (_,b) in bv]
    bids = [id for (id,_) in bv]
    bmap = Dict(id => i-1 for (i,id) in enumerate(bids))

    gv = sort([(parse(Int,k), g) for (k,g) in data["gen"]]; by=first)
    gv = filter(t -> Int(get(t[2], "gen_status", get(t[2], "status", 1))) == 1, gv)
    gf = [Float64[g["mbase"], get(g,"pg",0.0), g["pmin"], g["pmax"], get(g,"qg",0.0),
                  g["qmin"], g["qmax"], get(g,"vg",1.0), _gcost(g)...] for (_,g) in gv]

    lv = sort([(parse(Int,k), l) for (k,l) in get(data, "load", Dict{String,Any}())]; by=first)
    lv = filter(t -> get(t[2], "status", 1) != 0, lv)
    lf = [[l["pd"], l["qd"]] for (_,l) in lv]

    sv = sort([(parse(Int,k), s) for (k,s) in get(data, "shunt", Dict{String,Any}())]; by=first)
    sv = filter(t -> get(t[2], "status", 1) != 0, sv)
    sf = [[s["bs"], s["gs"]] for (_,s) in sv]

    brv = sort([(parse(Int,k), b) for (k,b) in get(data, "branch", Dict{String,Any}())]; by=first)
    brv = filter(t -> get(t[2], "br_status", 1) != 0, brv)
    acs, acr, acf = Int[], Int[], Vector{Float64}[]
    trs, trr, trf = Int[], Int[], Vector{Float64}[]
    acid, trid = Int[], Int[]
    for (bid,b) in brv
        u, v = bmap[b["f_bus"]], bmap[b["t_bus"]]
        ra, rbb, rc = _rates(b)
        amin, amax = get(b, "angmin", -π/3), get(b, "angmax", π/3)
        if _is_xfmr(b)
            push!(trs, u); push!(trr, v); push!(trid, bid)
            push!(trf, Float64[amin, amax, b["br_r"], b["br_x"], ra, rbb, rc,
                               get(b,"tap",1.0), get(b,"shift",0.0),
                               get(b,"b_fr",0.0), get(b,"b_to",0.0)])
        else
            push!(acs, u); push!(acr, v); push!(acid, bid)
            push!(acf, Float64[amin, amax, get(b,"b_fr",0.0), get(b,"b_to",0.0),
                               b["br_r"], b["br_x"], ra, rbb, rc])
        end
    end

    gls = collect(0:length(gv)-1); glr = [bmap[g["gen_bus"]] for (_,g) in gv]
    lls = collect(0:length(lv)-1); llr = [bmap[l["load_bus"]] for (_,l) in lv]
    sls = collect(0:length(sv)-1); slr = [bmap[s["shunt_bus"]] for (_,s) in sv]

    sb = [[0.0, 1.0] for _ in bv]
    sg = [[0.0, 0.0] for _ in gv]
    sacf = [Float64[0,0,0,0] for _ in acs]
    strf = [Float64[0,0,0,0] for _ in trs]

    opf = OrderedDict(
        "grid" => OrderedDict(
            "nodes" => OrderedDict("bus"=>bf, "generator"=>gf, "load"=>lf, "shunt"=>sf),
            "edges" => OrderedDict(
                "ac_line" => OrderedDict("senders"=>acs, "receivers"=>acr, "features"=>acf),
                "transformer" => OrderedDict("senders"=>trs, "receivers"=>trr, "features"=>trf),
                "generator_link" => OrderedDict("senders"=>gls, "receivers"=>glr),
                "load_link" => OrderedDict("senders"=>lls, "receivers"=>llr),
                "shunt_link" => OrderedDict("senders"=>sls, "receivers"=>slr),
            ),
            "context" => [[[data["baseMVA"]]]],
        ),
        "solution" => OrderedDict(
            "nodes" => OrderedDict("bus"=>sb, "generator"=>sg),
            "edges" => OrderedDict(
                "ac_line" => OrderedDict("senders"=>acs, "receivers"=>acr, "features"=>sacf),
                "transformer" => OrderedDict("senders"=>trs, "receivers"=>trr, "features"=>strf),
            ),
            "duals" => OrderedDict(
                "bus" => [Float64[0,0,0,0] for _ in bv],
                "generator" => [Float64[0,0,0,0] for _ in gv],
                "ac_line" => [Float64[0,0] for _ in acs],
                "transformer" => [Float64[0,0] for _ in trs],
            ),
        ),
        "metadata" => OrderedDict(
            "objective" => nothing,
            "termination_status" => "UNSOLVED_CONVERSION_ONLY",
            "bus_id_map" => bids,
            "gen_id_map" => [id for (id,_) in gv],
            "load_id_map" => [id for (id,_) in lv],
            "gen_bus_map" => [g["gen_bus"] for (_,g) in gv],
            "load_bus_map" => [l["load_bus"] for (_,l) in lv],
            "ac_line_branch_ids" => acid,
            "transformer_branch_ids" => trid,
            "conversion_assumptions" => [
                "parse_file import_all=false validate=true",
                "forced angmin/angmax = +/- pi/3 after parse",
                "offline gens excluded",
                "xfmr via tap!=0/1 or shift!=0",
                "rate_b/c fallback to rate_a",
                "solution zeros (no solve)",
            ],
        ),
    )
    return opf
end

function force_angle_limits!(data)
    for (_,b) in data["branch"]
        b["angmin"] = -π/3
        b["angmax"] =  π/3
    end
end

function main()
    if length(ARGS) < 2
        println("Usage: mpc_to_pyg.jl input.m output.pyg.json [--solve]")
        exit(2)
    end
    input_path = ARGS[1]
    output_path = ARGS[2]
    do_solve = "--solve" in ARGS

    data = PowerModels.parse_file(input_path; import_all=false, validate=true)
    force_angle_limits!(data)

    if do_solve
        # include official exporter if available
        export_jl = joinpath(@__DIR__, "..", "repos", "gridsfm", "power_grid", "US",
                             "topology_solver_pipeline", "export_gridsfm_data.jl")
        include(export_jl)
        n_bus = length(data["bus"])
        max_iter = n_bus > 1000 ? 5000 : 3000
        solver = optimizer_with_attributes(Ipopt.Optimizer,
            "print_level"=>0, "max_iter"=>max_iter, "tol"=>1e-8, "constr_viol_tol"=>1e-8)
        pm = PowerModels.instantiate_model(data, ACPPowerModel, PowerModels.build_opf)
        result = PowerModels.optimize_model!(pm, optimizer=solver)
        opf, feas = build_gridsfm_data(pm, result, data)
        println("solved feas=$feas obj=$(get(result,"objective",NaN)) status=$(result["termination_status"])")
    else
        opf = build_grid_only(data)
    end

    mkpath(dirname(output_path))
    open(output_path, "w") do io
        JSON3.pretty(io, opf)
    end
    println("Wrote $output_path nbus=$(length(data["bus"])) ngen_active=$(length(opf["grid"]["nodes"]["generator"]))")
end

