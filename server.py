from __future__ import annotations

import dataclasses
import datetime
import json
import os
from pathlib import Path

import minizinc
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

mcp = MCPServer(
    name="MiniZinc",
    description="Provides tools for analyzing and execution for MiniZinc models.",
)

DEFAULT_SOLVER = "gecode"


def _set_params(instance: minizinc.Instance, params) -> None:
    """Assign model parameters to a MiniZinc instance.

    Accepts either a dict mapping parameter names to values (as given in a .dzn
    file) or a JSON string encoding such an object.
    """
    if isinstance(params, str):
        params = json.loads(params)
    if not isinstance(params, dict):
        raise ValueError("params must be a JSON object mapping parameter names to values")
    for name, value in params.items():
        instance[name] = value


def _solution_to_dict(solution: minizinc.Instance.Solution) -> dict:
    return {
        key: value
        for key, value in dataclasses.asdict(solution).items()
        if not key.startswith("_")
    }


def _statistics_to_dict(statistics: dict) -> dict:
    result = {}
    for key, value in statistics.items():
        if isinstance(value, datetime.timedelta):
            result[key] = value.total_seconds()
        else:
            result[key] = value
    return result


_MZN_TYPE_NAMES = {int: "int", bool: "bool", float: "float", str: "string"}


def _type_str(t) -> str:
    """Render a Python type (as returned by Instance.analyse) as a short type string."""
    if isinstance(t, type):
        return _MZN_TYPE_NAMES.get(t, t.__name__)
    origin = getattr(t, "__origin__", None)
    args = getattr(t, "__args__", ())
    if origin is not None:
        name = getattr(origin, "__name__", str(origin))
        if name == "list":
            return "array of " + (_type_str(args[0]) if args else "?")
        if name == "set":
            return "set of " + (_type_str(args[0]) if args else "?")
        if args:
            return f"{name}[{', '.join(_type_str(a) for a in args)}]"
        return name
    return str(t)


def _result_to_dict(result: minizinc.Result) -> dict:
    payload = {"status": str(result.status), "statistics": _statistics_to_dict(result.statistics)}
    if result.objective is not None:
        payload["objective"] = result.objective
    if len(result) == 1 and result.solution is not None:
        payload["solution"] = _solution_to_dict(result.solution)
    elif len(result) > 1:
        payload["solutions"] = [_solution_to_dict(result[i]) for i in range(len(result))]
    return payload


@mcp.tool(
    name="list_solvers",
    description="List MiniZinc solvers",
    annotations=ToolAnnotations(open_world_hint=False),
)
def list_solvers() -> list[str]:
    """List all MiniZinc solvers available on this machine, as tag names usable as the
    `solver` argument of solve_model."""
    return list(minizinc.default_driver.available_solvers().keys())


@mcp.tool(
    name="validate_model",
    description="Validate a MiniZinc model",
    annotations=ToolAnnotations(open_world_hint=False),
)
def validate_model(model_code: str, params: dict | None = None) -> dict:
    """Parse and type-check a MiniZinc model without solving it.

    Args:
        model_code: The MiniZinc (.mzn) source code of the model.
        params: Optional object mapping parameter names to values (as given in a
            .dzn file). Used to type-check parameters.
    """
    try:
        model = minizinc.Model()
        model.add_string(model_code)
        instance = minizinc.Instance(minizinc.Solver.lookup(DEFAULT_SOLVER), model)
        if params:
            _set_params(instance, params)
        return {"status": "VALID", "message": "Model parsed and type-checked successfully."}
    except Exception as exc:
        return {"status": "INVALID", "error": str(exc)}


@mcp.tool(
    name="solve_model",
    description="Solve a MiniZinc model",
    annotations=ToolAnnotations(open_world_hint=False),
)
def solve_model(
    model_code: str,
    params: dict | None = None,
    solver: str = DEFAULT_SOLVER,
    all_solutions: bool = False,
    max_solutions: int | None = None,
    timeout_seconds: int | None = None,
) -> dict:
    """Solve a MiniZinc constraint model given as source code.

    Args:
        model_code: The MiniZinc (.mzn) source code of the model.
        params: Optional object mapping parameter names to values, like a .dzn
            file. JSON arrays map to MiniZinc arrays; numbers, strings and
            booleans map to their native MiniZinc types.
        solver: Name of the MiniZinc solver to use (see list_solvers). Defaults to
            "gecode".
        all_solutions: If True, compute all solutions of a satisfy problem.
        max_solutions: Stop after finding at most this many solutions.
        timeout_seconds: Time limit for the solver in seconds.

    Returns:
        A dict with status (e.g. OPTIMAL_SOLUTION, SATISFIED, UNSATISFIABLE, UNKNOWN),
        the solution(s) if any, the objective value for optimization problems, and
        solver statistics. On error, a dict with status "ERROR" and an error message.
    """
    try:
        model = minizinc.Model()
        model.add_string(model_code)
        solver_obj = minizinc.Solver.lookup(solver)
        instance = minizinc.Instance(solver_obj, model)
        if params:
            _set_params(instance, params)

        solve_kwargs = {}
        if all_solutions:
            solve_kwargs["all_solutions"] = True
        if max_solutions is not None:
            solve_kwargs["nr_solutions"] = max_solutions
        if timeout_seconds is not None:
            solve_kwargs["timeout"] = datetime.timedelta(seconds=timeout_seconds)

        result = instance.solve(**solve_kwargs)
        return _result_to_dict(result)
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


@mcp.tool(
    name="solve_model_by_path",
    description="Solve a MiniZinc model given by file paths",
    annotations=ToolAnnotations(open_world_hint=False),
)
def solve_model_by_path(
    model_path: str,
    data_path: str | None = None,
    solver: str = DEFAULT_SOLVER,
    all_solutions: bool = False,
    max_solutions: int | None = None,
    timeout_seconds: int | None = None,
) -> dict:
    """Solve a MiniZinc constraint model given by file paths.

    Args:
        model_path: Path to the MiniZinc (.mzn) model file.
        data_path: Optional path to a data file (.dzn) with parameter values.
        solver: Name of the MiniZinc solver to use (see list_solvers). Defaults to
            "gecode".
        all_solutions: If True, compute all solutions of a satisfy problem.
        max_solutions: Stop after finding at most this many solutions.
        timeout_seconds: Time limit for the solver in seconds.

    Returns:
        A dict with status (e.g. OPTIMAL_SOLUTION, SATISFIED, UNSATISFIABLE, UNKNOWN),
        the solution(s) if any, the objective value for optimization problems, and
        solver statistics. On error, a dict with status "ERROR" and an error message.
    """
    try:
        if not os.path.exists(model_path):
            raise FileNotFoundError(model_path)
        if data_path and not os.path.exists(data_path):
            raise FileNotFoundError(data_path)
        model = minizinc.Model(model_path)
        instance = minizinc.Instance(minizinc.Solver.lookup(solver), model)
        if data_path:
            instance.add_file(data_path)

        solve_kwargs = {}
        if all_solutions:
            solve_kwargs["all_solutions"] = True
        if max_solutions is not None:
            solve_kwargs["nr_solutions"] = max_solutions
        if timeout_seconds is not None:
            solve_kwargs["timeout"] = datetime.timedelta(seconds=timeout_seconds)

        result = instance.solve(**solve_kwargs)
        return _result_to_dict(result)
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


@mcp.tool(
    name="get_model_info",
    description="Describe a MiniZinc model without solving it",
    annotations=ToolAnnotations(open_world_hint=False),
)
def get_model_info(model_code: str, params: dict | str | None = None) -> dict:
    """Parse a MiniZinc model and return its solve method, declared parameters,
    and output variables with their types, without solving it.

    Args:
        model_code: The MiniZinc (.mzn) source code of the model.
        params: Optional parameter assignments (dict or JSON string), used to
            type-check already-assigned parameters.

    Returns:
        A dict with "method" (satisfy/minimize/maximize), "input" mapping
        parameter names to type strings, and "output" mapping variable names
        to type strings. On error, a dict with status "ERROR" and an error
        message.
    """
    try:
        model = minizinc.Model()
        model.add_string(model_code)
        instance = minizinc.Instance(minizinc.Solver.lookup(DEFAULT_SOLVER), model)
        if params:
            _set_params(instance, params)
        instance.analyse()
        return {
            "method": instance.method.name.lower(),
            "input": {name: _type_str(t) for name, t in instance.input.items()},
            "output": {
                name: _type_str(t)
                for name, t in instance.output.items()
                if not name.startswith("_")
            },
        }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


@mcp.tool(
    name="get_flatzinc",
    description="Flatten a MiniZinc model to FlatZinc without solving it",
    annotations=ToolAnnotations(open_world_hint=False),
)
def get_flatzinc(
    model_code: str,
    params: dict | str | None = None,
    optimisation_level: int | None = None,
) -> dict:
    """Compile a MiniZinc model (and optional data) to FlatZinc text.

    Args:
        model_code: The MiniZinc (.mzn) source code of the model.
        params: Optional parameter assignments (dict or JSON string).
        optimisation_level: MiniZinc compiler optimisation level 0-5.

    Returns:
        A dict with "flat_model" (the .fzn text), "output_model" (the .ozn
        text) and "statistics" from flattening. On error, a dict with status
        "ERROR" and an error message.
    """
    try:
        model = minizinc.Model()
        model.add_string(model_code)
        instance = minizinc.Instance(minizinc.Solver.lookup(DEFAULT_SOLVER), model)
        if params:
            _set_params(instance, params)
        with instance.flat(optimisation_level=optimisation_level) as (fzn, ozn, statistics):
            return {
                "flat_model": Path(fzn.name).read_text(),
                "output_model": Path(ozn.name).read_text(),
                "statistics": _statistics_to_dict(statistics),
            }
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()