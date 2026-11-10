#!/usr/bin/env julia
# Usage: julia --project=... batch_mpc_to_pyg.jl list.csv out_dir
include(joinpath(@__DIR__, "mpc_to_pyg.jl"))
# mpc_to_pyg.jl calls main() at end — avoid double run by restructuring.
# Instead duplicate minimal convert loop using same functions after include fails.
# Safer: don't include file that auto-runs; copy convert API.
