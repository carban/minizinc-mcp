# MiniZinc MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes [MiniZinc](https://www.minizinc.org/) constraint solving and optimization to LLM clients such as opencode. It lets an agent parse, type-check, and solve MiniZinc models directly from a chat session.

Built with the [MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/) and the [`.mzn` Python binding](https://pypi.org/project/minizinc/).

## Prerequisites

- Python 3.10+ (developed against 3.14)
- [MiniZinc](https://www.minizinc.org/) 2.6+ with the `minizinc` executable on `PATH` (includes a default solver such as Gecode)
- [uv](https://docs.astral.sh/uv/) (dependency management; `pip` works too)

## What it does

The server exposes three tools:

| Tool | Description |
|---|---|
| `list_solvers` | Lists every MiniZinc solver installed on the machine. The returned tag names (e.g. `gecode`, `chuffed`, `highs`) can be passed to `solve_model`. |
| `validate_model` | Parses and type-checks MiniZinc model code **without solving it**. Useful for checking model syntax up front. Returns `VALID` or `INVALID` with an error message. |
| `solve_model` | Solves a MiniZinc model given as source code: once, exhaustively (`all_solutions`), or with a solution / time limit. Returns the status, solution(s), objective value (for optimization problems), and solver statistics. |
| `solve_model_by_path` | Same as `solve_model` but loads the model and its optional data (`.dzn`) file from paths instead of source code. |

### `solve_model` arguments

| Argument | Type | Default | Description |
|---|---|---|---|
| `model_code` | `str` | (required) | The MiniZinc source code (`.mzn`) of the model. |
| `params` | `dict \| str` | `None` | Parameter assignments like a `.dzn` file: a JSON object mapping names to values (a JSON string encoding such an object is also accepted). |
| `solver` | `str` | `"gecode"` | Which solver to use (see `list_solvers`). |
| `all_solutions` | `bool` | `False` | Compute all solutions of a `solve satisfy` problem. |
| `max_solutions` | `int \| None` | `None` | Stop after at most this many solutions. |
| `timeout_seconds` | `int \| None` | `None` | Solver time limit in seconds. |

The result is a JSON object like:

```json
{
  "status": "OPTIMAL_SOLUTION",
  "objective": 9,
  "solution": { "objective": 9, "x": 9, "y": 1 },
  "statistics": { "time": 0.204, "nodes": 3, ... }
}
```

`status` is one of `SATISFIED`, `OPTIMAL_SOLUTION`, `ALL_SOLUTIONS`, `UNSATISFIABLE`, `UNKNOWN`, or `ERROR`. `validate_model` and `solve_model` never raise in normal operation — errors are returned inside the result dict.

## Setup

```sh
uv sync          # create the environment and install mcp + minizinc
```

## Running standalone

The server speaks the MCP **stdio** transport, so it is launched as a subprocess by an MCP client. Run it like any other MCP server with the SDK inspector:

```sh
uv run mcp dev server.py
```

that opens the MCP Inspector in the browser where every tool can be called interactively. A minimal programmatic smoke test:

```sh
uv run python -c "
import asyncio
from mcp import Client
from mcp.client.stdio import StdioServerParameters

async def main():
    params = StdioServerParameters(command='uv', args=['run', 'python', 'server.py'], cwd='.')
    async with Client(params) as client:
        result = await client.call_tool('solve_model', {
            'model_code': 'var 1..10: x; var 1..10: y; constraint x + y = 10; solve maximize x;'
        })
        print(result.content[0].text)

asyncio.run(main())
"
```

## Using it with opencode

A project-level `opencode.jsonc` already registers the server:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "minizinc": {
      "type": "local",
      "command": ["uv", "run", "--project", ".", "python", "server.py"],
      "cwd": "."
    }
  }
}
```

Quit and restart opencode for the config to take effect. The tools then appear as `minizinc_list_solvers`, `minizinc_validate_model`, `minizinc_solve_model`, and `minizinc_solve_model_by_path`, and can be invoked from the chat prompt.

To register the server globally instead, add the same `mcp.minizinc` block to `~/.config/opencode/opencode.json` (or `opencode.jsonc`) and point `command` at the absolute path of `server.py`.

## Notes and limitations

- `params` follows JSON representation: JSON arrays map to MiniZinc arrays; numbers, strings, and booleans map to their native MiniZinc types. Exotic types like sets and enums are not fully expressible this way.
- Do not combine `all_solutions` with `max_solutions`; the MiniZinc driver rejects the combination.
- MiniZinc requires a solver that supports the model (e.g. `chuffed`/`gecode` for CP, `highs`/`cbc` for MIP models). Use `list_solvers` to see what is installed.
- Solutions are returned inline in the tool result; `read_only_hint` is set on all tools, so they do not modify your files or system.