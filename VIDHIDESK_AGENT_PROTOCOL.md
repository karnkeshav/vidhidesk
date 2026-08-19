# VIDHIDESK_AGENT_PROTOCOL.md

## ChatGPT → Claude Code → Oracle VM Controlled Execution Protocol

**Project:** VidhiDesk\
**Purpose:** Controlled migration and deployment of the VidhiDesk
FastAPI backend from Render to the existing Oracle VM while protecting
the existing `sensex-bot.service`.

------------------------------------------------------------------------

# 1. Purpose

This protocol defines the operating model between:

-   **ChatGPT** --- control, reasoning, review, approval, and prompt
    generation
-   **Claude Code** --- execution agent
-   **Oracle VM** --- target infrastructure
-   **GitHub** --- source repository
-   **Vercel** --- frontend
-   **Supabase** --- Auth, PostgreSQL, Storage

The protocol is designed to permit progressively automated execution
while maintaining strict protection around the existing Sensex bot.

The migration must be performed in explicit phases with gates between
phases.

------------------------------------------------------------------------

# 2. Current Infrastructure

## Oracle VM

``` text
Host:       152.67.165.226
User:       ubuntu
OS:         Ubuntu 24.04.4 LTS
CPU:        2 OCPU
RAM:        ~11 GiB
Disk:       ~45 GB total / ~36 GB available
Docker:     29.6.2
Architecture: x86_64
```

## Existing production workload

``` text
Service:
    sensex-bot.service

Working directory:
    /home/ubuntu/sensex-bot

Runtime:
    /home/ubuntu/sensex-bot/venv/bin/python3 main.py
```

This service is a protected workload.

## VidhiDesk target

``` text
/home/ubuntu/vidhidesk

Docker:
    vidhidesk-api
```

The Sensex bot and VidhiDesk must remain operationally isolated.

------------------------------------------------------------------------

# 3. Control Plane

## ChatGPT responsibilities

ChatGPT is the control and reasoning layer.

ChatGPT:

1.  Reviews execution reports.
2.  Determines whether the current phase succeeded.
3.  Identifies failures and root causes.
4.  Generates the next Claude Code task.
5.  Defines the exact authorized scope.
6.  Defines stop conditions.
7.  Reviews diffs before deployment.
8.  Reviews benchmark results.
9.  Determines whether a phase can advance.
10. Requires human approval for defined high-risk operations.

ChatGPT does **not** blindly accept Claude Code recommendations.

------------------------------------------------------------------------

# 4. Execution Plane

## Claude Code responsibilities

Claude Code is the execution agent.

Claude Code may:

-   inspect repositories
-   inspect the Oracle VM
-   modify authorized files
-   build Docker images
-   run containers
-   execute tests
-   inspect logs
-   measure CPU/RAM
-   diagnose deployment failures
-   configure authorized deployment components

Claude Code must operate only within the scope supplied by ChatGPT.

If a requested operation conflicts with a protected resource or stop
condition, Claude Code must stop and report instead of improvising.

------------------------------------------------------------------------

# 5. Protected Resources

The following are permanently protected unless ChatGPT explicitly
authorizes a specific operation.

## Sensex bot

``` text
/home/ubuntu/sensex-bot/**
/etc/systemd/system/sensex-bot.service
```

Protected service:

``` text
sensex-bot.service
```

## Forbidden operations against Sensex

Claude Code must NOT:

-   stop the service
-   restart the service
-   disable the service
-   enable the service
-   modify its unit file
-   modify its Python environment
-   modify its source
-   modify its configuration
-   kill its process
-   delete its files
-   change its Redis configuration
-   reboot the VM for Sensex-related reasons

If a migration task appears to require one of these operations, STOP and
report.

------------------------------------------------------------------------

# 6. Other Protected Infrastructure

Unless explicitly authorized, Claude Code must not modify:

``` text
Vercel
Supabase
Render
Oracle Cloud networking
Oracle security lists
DNS
firewall
SSH configuration
system-wide package configuration
```

Claude Code may inspect these resources where necessary.

------------------------------------------------------------------------

# 7. Repository Scope

VidhiDesk repository:

``` text
https://github.com/karnkeshav/vidhidesk.git
```

Target Oracle location:

``` text
/home/ubuntu/vidhidesk
```

The repository currently contains:

``` text
api/
web/
templates/
corpus/
docs/
```

The frontend remains on Vercel.

The backend is the migration target.

------------------------------------------------------------------------

# 8. Runtime Standard

The project-standard backend runtime is:

``` text
Python 3.11.10
```

Use:

``` text
python:3.11.10-slim
```

for the Docker base image unless a later approved decision changes this.

The following files are expected to use Python 3.11.10:

``` text
runtime.txt
api/runtime.txt
api/.python-version
```

Do not change the project's documented 3.11 standards.

------------------------------------------------------------------------

# 9. Target Architecture

``` text
                         ┌──────────────────────┐
                         │       Vercel         │
                         │   Next.js frontend   │
                         └──────────┬───────────┘
                                    │ HTTPS
                                    ▼
              ┌───────────────────────────────────────────┐
              │              Oracle VM                    │
              │                                           │
              │  ┌─────────────────────────────────────┐  │
              │  │      sensex-bot.service             │  │
              │  │      PROTECTED / UNCHANGED           │  │
              │  └─────────────────────────────────────┘  │
              │                                           │
              │  ┌─────────────────────────────────────┐  │
              │  │      Docker: vidhidesk-api          │  │
              │  │      FastAPI / Uvicorn :8000        │  │
              │  └──────────────────┬──────────────────┘  │
              │                     │                     │
              │              HTTPS / outbound             │
              └─────────────────────┼─────────────────────┘
                                    │
                                    ▼
                             ┌─────────────┐
                             │  Supabase   │
                             │ Auth / DB   │
                             │ Storage     │
                             └─────────────┘
```

HTTPS termination strategy is intentionally deferred until the local
container has passed validation and benchmarking.

------------------------------------------------------------------------

# 10. VidhiDesk Container Resource Policy

Initial deployment recommendation:

``` text
CPU limit:
    1.0 CPU

Memory limit:
    2 GB

Memory reservation:
    1 GB

Restart:
    unless-stopped
```

These are initial safety limits, not permanent performance limits.

They exist primarily to prevent VidhiDesk from consuming the entire VM
and affecting Sensex.

The limits may be changed only after benchmark evidence and ChatGPT
approval.

------------------------------------------------------------------------

# 11. Phase Model

## Phase 0 --- Environment Discovery

Purpose:

Establish connectivity and infrastructure facts.

Actions:

-   identify VM
-   inspect OS
-   inspect CPU/RAM/disk
-   inspect Docker
-   inspect systemd
-   inspect Sensex
-   inspect ports

Status:

COMPLETED.

------------------------------------------------------------------------

## Phase 1 --- Forensic Inspection

Purpose:

Understand the existing application and infrastructure without making
changes.

Actions:

-   inspect repository
-   inspect backend
-   inspect dependencies
-   inspect environment variables
-   inspect Render configuration available locally
-   inspect Docker readiness
-   inspect resource usage
-   inspect Sensex protection requirements

Status:

COMPLETED.

Result:

CONDITIONAL GO.

------------------------------------------------------------------------

## Phase 2A --- Python Resolution

Purpose:

Resolve runtime ambiguity before containerization.

Decision:

``` text
Python 3.11.10
```

Status:

COMPLETED.

------------------------------------------------------------------------

## Phase 2B --- Repository Preparation

Authorized actions:

-   correct Python runtime files
-   create `api/Dockerfile`
-   create or update `.dockerignore`
-   validate Docker build context
-   inspect git diff
-   run safe tests

Forbidden:

-   Oracle changes
-   Docker deployment
-   Vercel changes
-   Render changes
-   Supabase changes
-   Sensex changes
-   git push

Gate:

ChatGPT reviews the diff and test result.

------------------------------------------------------------------------

## Phase 2C --- Oracle Staging

Authorized actions:

-   create `/home/ubuntu/vidhidesk`
-   clone approved Git revision
-   provision secrets using approved secure mechanism
-   build Docker image
-   run container on localhost/host port
-   configure generated-draft persistence
-   execute health checks
-   inspect container logs
-   inspect resource usage

Initial container:

``` text
name:
    vidhidesk-api

port:
    8000

CPU:
    1.0

Memory:
    2 GB
```

Forbidden:

-   stopping/restarting Sensex
-   modifying Sensex
-   public exposure
-   Vercel cutover
-   deleting Render
-   changing DNS

Gate:

Local health and functional tests must pass.

------------------------------------------------------------------------

## Phase 3 --- Performance Benchmark

Purpose:

Determine whether Oracle solves the Render CPU bottleneck.

Compare the same workload against:

``` text
Render baseline
Oracle container
```

Important baseline:

``` text
~148 seconds total draft generation
~85 seconds first PII NER inference
~60 seconds Gemini generation
```

Measure:

-   total latency
-   PII NER latency
-   RAG latency
-   document generation latency
-   Gemini latency
-   CPU
-   memory
-   concurrent request behavior
-   Sensex CPU/memory during benchmark

Do not declare migration successful based solely on health checks.

Gate:

ChatGPT reviews benchmark results.

------------------------------------------------------------------------

## Phase 4 --- Public HTTPS

Only after Phase 3 passes.

Potential strategies:

-   reverse proxy
-   Cloudflare Tunnel
-   other approved HTTPS mechanism

Selection criteria:

-   HTTPS
-   long-running request support
-   suitable timeout
-   minimal attack surface
-   does not interfere with Sensex
-   rollback simplicity

No Vercel change until external endpoint validation succeeds.

------------------------------------------------------------------------

## Phase 5 --- External API Validation

Test the Oracle-hosted API externally.

Required:

``` text
/health
authentication
matters
templates
RAG
PII
draft generation
document retrieval
```

Validate:

-   CORS
-   JWT
-   Supabase RLS
-   long requests
-   generated documents
-   errors
-   logs

------------------------------------------------------------------------

## Phase 6 --- Vercel Integration

Change:

``` text
NEXT_PUBLIC_API_URL
```

from Render to the validated Oracle HTTPS endpoint.

Do not remove Render yet.

Validate frontend workflows end-to-end.

Gate:

Human approval required before production cutover.

------------------------------------------------------------------------

## Phase 7 --- Production Cutover

Only after:

-   Oracle benchmark passes
-   external tests pass
-   frontend tests pass
-   rollback is verified
-   Sensex remains healthy
-   monitoring is available

Then Oracle becomes the active backend.

Render remains available as rollback until the migration is formally
closed.

------------------------------------------------------------------------

# 12. Change Authorization Model

Every Claude Code task must contain:

``` text
TASK_ID
PHASE
OBJECTIVE
AUTHORIZED_PATHS
AUTHORIZED_COMMAND_CLASSES
PROTECTED_PATHS
FORBIDDEN_ACTIONS
STOP_CONDITIONS
VALIDATION_REQUIREMENTS
REPORT_FORMAT
```

Claude Code must not infer additional authority.

------------------------------------------------------------------------

# 13. Standard Claude Code Task Envelope

Every execution prompt should use this structure:

``` text
VIDHIDESK AGENT TASK

TASK_ID:
PHASE:

OBJECTIVE:

AUTHORIZED SCOPE:

AUTHORIZED PATHS:

PROTECTED PATHS:

FORBIDDEN ACTIONS:

ALLOWED COMMAND CLASSES:

STOP CONDITIONS:

REQUIRED VALIDATION:

REQUIRED REPORT:

DO NOT PROCEED BEYOND:
```

------------------------------------------------------------------------

# 14. Standard Claude Code Report

Claude Code must return:

``` text
VIDHIDESK AGENT REPORT

TASK_ID:

STATUS:
SUCCESS | PARTIAL | FAILED | BLOCKED

PHASE:

FILES_CHANGED:

FILES_CREATED:

FILES_DELETED:

COMMANDS_EXECUTED:

SERVICES_TOUCHED:

DOCKER_CHANGES:

TESTS_RUN:

TEST_RESULTS:

RESOURCE_USAGE:

LOG_SUMMARY:

ERRORS:

WARNINGS:

SECURITY_NOTES:

PROTECTED_RESOURCE_STATUS:

ROLLBACK_REQUIRED:
YES | NO

NEXT_RECOMMENDED_ACTION:

STOPPED_AT:
```

Claude Code must never claim success without evidence.

------------------------------------------------------------------------

# 15. Stop Conditions

Claude Code must STOP immediately if:

1.  A protected Sensex resource must be modified.
2.  A destructive command appears necessary.
3.  A secret value is required but unavailable.
4.  A required file lies outside authorized paths.
5.  Oracle networking must be changed but is not authorized.
6.  Firewall rules must change but are not authorized.
7.  The Docker build requires unexpected system-level changes.
8.  Tests fail in a way that requires unrelated code changes.
9.  Resource usage threatens VM stability.
10. Sensex CPU/RAM behavior changes unexpectedly.
11. A service unexpectedly stops.
12. A command could reboot the VM.
13. A command could delete infrastructure.
14. Claude Code is uncertain whether an action is safe.

On STOP:

Do not improvise.

Report the blocker to ChatGPT.

------------------------------------------------------------------------

# 16. Safety Checks Before Every Oracle Deployment Action

Before modifying Oracle, Claude Code must verify:

``` text
sensex-bot.service = active/running

Sensex process exists

Sensex PID unchanged unless explicitly expected

Sensex CPU reasonable

Sensex memory reasonable

Available RAM reasonable

Disk free space reasonable

Docker daemon active
```

After each major VidhiDesk deployment action, repeat the Sensex checks.

------------------------------------------------------------------------

# 17. Secret Handling

Secrets must never be:

-   committed
-   pushed
-   printed
-   included in Dockerfile
-   included in Docker image layers
-   pasted into reports
-   exposed in logs

Expected runtime secrets include:

``` text
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_KEY
GEMINI_API_KEY
GROQ_API_KEY
SAMBANOVA_API_KEY
CEREBRAS_API_KEY
INDIAN_KANOON_API_TOKEN
```

Only variable names may appear in reports.

Preferred deployment mechanism:

``` text
protected environment file
```

with restrictive filesystem permissions.

------------------------------------------------------------------------

# 18. Docker Rules

The VidhiDesk image must:

-   use Python 3.11.10
-   install `api/requirements.txt`
-   include `templates/`
-   include `corpus/`
-   expose FastAPI on `0.0.0.0:8000`
-   include `/health` healthcheck
-   exclude secrets
-   exclude generated runtime artifacts
-   not include `.git`
-   not include local virtual environments

Generated documents must be persisted outside the image.

------------------------------------------------------------------------

# 19. Git Rules

Claude Code may modify Git working trees only when authorized.

Default:

``` text
No git push
No force push
No destructive reset
No git clean
No branch deletion
```

A commit requires explicit authorization.

A push requires explicit authorization.

------------------------------------------------------------------------

# 20. Rollback Strategy

Render remains active during migration.

Rollback hierarchy:

### Application rollback

Stop/remove only the VidhiDesk container and restore the previous
container/image.

### Vercel rollback

Restore:

``` text
NEXT_PUBLIC_API_URL
```

to Render.

### Infrastructure rollback

Do not touch:

``` text
sensex-bot.service
```

Rollback must never require stopping Sensex.

------------------------------------------------------------------------

# 21. Human Approval Gates

Human approval is mandatory for:

-   production cutover
-   Vercel API URL change
-   public firewall exposure
-   DNS changes
-   secret provisioning if not pre-approved
-   modifying Oracle security lists
-   stopping Render
-   deleting Render resources
-   changing Sensex configuration
-   rebooting the Oracle VM
-   deleting Docker volumes containing production data
-   deleting production data

------------------------------------------------------------------------

# 22. Automated Actions That May Be Allowed

Once the protocol is established and the task scope explicitly permits
it, Claude Code may automate:

-   repository inspection
-   Dockerfile creation
-   Docker builds
-   container creation
-   container restart
-   health checks
-   test execution
-   log collection
-   CPU/RAM measurement
-   Docker resource inspection
-   non-destructive diagnostics
-   application deployment
-   application rollback

------------------------------------------------------------------------

# 23. ChatGPT Decision Logic

After receiving every Claude Code report:

## PASS

If all requirements passed:

``` text
ChatGPT generates next phase task.
```

## PARTIAL

If implementation partially succeeded:

``` text
ChatGPT diagnoses missing work.
ChatGPT generates corrective task.
```

## FAILED

If the task failed:

``` text
ChatGPT analyzes root cause.
No automatic progression.
```

## BLOCKED

If a protected resource or authorization boundary was encountered:

``` text
STOP.
Ask for authorization or change the plan.
```

## UNEXPECTED

If Claude reports anything outside the planned architecture:

``` text
STOP.
Review manually.
```

------------------------------------------------------------------------

# 24. Performance Acceptance Criteria

The migration is not successful merely because the container starts.

Minimum acceptance criteria:

1.  `/health` works.
2.  Authentication works.
3.  Supabase access works.
4.  RAG works.
5.  PII masking works.
6.  Document generation works.
7.  Generated documents persist.
8.  Long-running requests survive proxy timeout.
9.  CPU/RAM remain within limits.
10. Sensex remains healthy.
11. Oracle latency is materially better than Render where CPU was the
    bottleneck.
12. No production secrets are exposed.

The actual performance target must be based on measured Oracle results
rather than an invented number.

------------------------------------------------------------------------

# 25. Monitoring During Migration

At minimum monitor:

``` text
docker stats

free -h

df -h

uptime

systemctl status sensex-bot.service

ps/process resource usage
```

During benchmarks, record:

``` text
VidhiDesk CPU
VidhiDesk memory
VM CPU
VM memory
Sensex CPU
Sensex memory
request latency
NER latency
LLM latency
```

------------------------------------------------------------------------

# 26. Operating Principle

The system follows this rule:

> **ChatGPT decides what should happen. Claude Code determines how to
> execute the authorized task. The Oracle VM executes only within the
> authorized boundary.**

Claude Code is not the final authority.

ChatGPT is not granted direct production access.

The Oracle VM is protected by explicit technical and procedural
boundaries.

------------------------------------------------------------------------

# 27. Current State

As of the initial migration:

``` text
Render backend:
    ACTIVE

Oracle VM:
    ACTIVE

Sensex bot:
    ACTIVE

Docker:
    READY

VidhiDesk Docker:
    NOT DEPLOYED

HTTPS:
    NOT CONFIGURED

Vercel:
    UNCHANGED

Supabase:
    UNCHANGED
```

Migration state:

``` text
Phase 0: COMPLETE
Phase 1: COMPLETE
Phase 2A: COMPLETE
Phase 2B: NEXT
Phase 2C: NOT STARTED
```

Current decision:

``` text
CONDITIONAL GO
```

------------------------------------------------------------------------

# 28. Future Extension --- Automated Controller

A future controller may automate the exchange:

``` text
ChatGPT
   |
   | Task specification
   v
Execution Bridge
   |
   v
Claude Code
   |
   | Execution
   v
Oracle VM
   |
   | Report
   v
Execution Bridge
   |
   v
ChatGPT
```

The bridge should preserve:

-   task IDs
-   phase IDs
-   authorization scope
-   command logs
-   execution output
-   exit codes
-   changed files
-   resource metrics
-   timestamps

The bridge must not bypass the protected-resource rules.

------------------------------------------------------------------------

# 29. First Approved Next Task

The current next task is:

``` text
PHASE 2B

Correct Python runtime files to 3.11.10.

Create api/Dockerfile.

Create/update .dockerignore.

Run safe repository validation.

Do not deploy.

Do not access Oracle.

Do not modify Sensex.

Do not push.
```

After completion:

``` text
STOP

Return the standard Claude Code report.

Wait for ChatGPT review.
```
