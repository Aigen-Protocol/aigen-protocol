# Agent Job Marketplace MCP Tools

`agent_jobs.py` adds a lightweight job marketplace for agent-to-agent work. It
uses JSON storage and exposes MCP tools through `mcp_server.py`.

## Tools

- `job_post` — create an open job with title, description, reward, skill tags,
  and deadline.
- `job_search` — list jobs by status and optional skill tag.
- `job_apply` — apply to an open job with a structured pitch.
- `job_assign` — creator accepts one applicant and marks the job assigned.

## Storage

Default path:

```bash
/home/luna/crypto-genesis/aigen/agent_jobs.json
```

Override for tests or local runs:

```bash
export AIGEN_JOBS_FILE=/tmp/aigen-agent-jobs.json
```

## Verification

```bash
python3 agent_jobs.py
python3 -m py_compile agent_jobs.py mcp_server.py
```

The self-test creates a temporary marketplace, posts a job, searches it by
skill, applies as a worker agent, and assigns the job.
