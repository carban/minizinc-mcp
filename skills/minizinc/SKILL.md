---
name: minizinc
description: Use when the user asks to model, formulate, validate, or solve a constraint satisfaction/problem, constraint programming (CP), combinatorial, or optimization problem (scheduling, packing, routing, assignment, knapsack, graphs, Sudoku, etc.) with MiniZinc. Drives the minizinc_* MCP tools type-checking models, running solvers, and presenting results as Markdown tables.
---

# MiniZinc Skill

Use the `minizinc_*` MCP tools to model, check, and solve constraint problems with MiniZinc, and present the results as Markdown tables.

## When to use

- Constraint satisfaction problems (CSP) and constraint programming (CP): scheduling, timetabling, resource allocation, Sudoku and puzzles, graph problems (coloring, matching).
- Combinatorial problems: knapsack, bin-packing, assignment, routing and TSP, subsets/selections.
- Optimization problems with a `minimize`/`maximize` objective, including mixed-integer and linear programs (MIP/LP).
- Validating, debugging, or understanding an existing `.mzn` model.

## Modeling workflow

1. Identify the decision variables, their domains, the constraints, and the objective (if any). Choose the `solve satisfy`, `solve minimize`, or `solve maximize` form accordingly.
2. Prefer `solve_model` with `model_code` unless the model or data already live in files, in which case use `solve_model_by_path`.
3. `params` follows JSON representation: JSON arrays map to MiniZinc arrays; numbers, strings, and booleans map to their native MiniZinc types. Sets and enums are not fully expressible this way.

## Tools

- `minizinc_list_tools` — List the tools exposed by this MiniZinc MCP server.
- `minizinc_list_solvers` — List installed solvers before solving. Use `gecode`/`chuffed` for CP models and `highs`/`cbc` for MIP/LP models.
- `minizinc_get_model_info` — Inspect a model without solving it: its solve method and the declared input parameters and output variables with types. Use this first when handed a model you must call with `params`.
- `minizinc_validate_model` — Parse and type-check `model_code` (with optional `params`) after writing or editing a model. Fast feedback without solving.
- `minizinc_solve_model` — Solve a model given as source code. Pass `params` as a dict, choose `solver`, `all_solutions` for a `solve satisfy` problem, `max_solutions` and `timeout_seconds` to bound the run.
- `minizinc_solve_model_by_path` — Like `solve_model` but loads the model and optional data (`.dzn`) file from paths.
- `minizinc_get_flatzinc` — Flatten a model to FlatZinc without solving it. Use for low-level debugging and inspection.

## Interpreting results

- `OPTIMAL_SOLUTION` — proven optimum for an optimization model; report the objective value.
- `SATISFIED` — a feasible solution was found for a satisfy model.
- `ALL_SOLUTIONS` — exhaustive enumeration of a satisfy model completed.
- `UNSATISFIABLE` — no solution exists; suggest relaxing constraints or widening domains.
- `UNKNOWN` — the solver gave up (usually timeout); consider a longer `timeout_seconds`, a different solver, or a reformulation.
- Errors come back as a result dict with `"status": "ERROR"` and an `"error"` message, not as exceptions.

## Presenting results

Never dump the raw JSON. Summarize the outcome, then render the output variables as Markdown tables: scalars as one row per variable, 1-D arrays as index/value rows, and multi-dimensional arrays as a grid with row and column indices. Include the objective value and key statistics (solve time, nodes) for optimization problems.

## Pitfalls

- Do not combine `all_solutions` with `max_solutions`; the MiniZinc driver rejects the combination.
- Pick a solver that supports the model: CP solvers (`gecode`, `chuffed`) for constraint models, MIP solvers (`highs`, `cbc`) for linear/integer problems.