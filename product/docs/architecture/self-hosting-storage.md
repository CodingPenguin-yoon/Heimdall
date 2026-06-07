# Self-hosting Storage Architecture

## Decision Summary

This document defines the storage model for running Heimdall inside Docker,
including the nested design where one Heimdall instance deploys another
Heimdall instance.

Current implementation:

- The API supports `HEIMDALL_RUNTIME_DIR`, `HEIMDALL_DATABASE_URL`,
  `HEIMDALL_PUBLIC_BASE_URL`, `HEIMDALL_PREVIEW_HOST`,
  `HEIMDALL_PREVIEW_PORT_START`, `HEIMDALL_PREVIEW_PORT_END`,
  provider token/webhook environment variables,
  `HEIMDALL_GITLAB_BASE_URL`, `HEIMDALL_REPO_ROOT`,
  `HEIMDALL_VOLUME_ROOT_HOST`, `HEIMDALL_VOLUME_ROOT_CONTAINER`,
  `HEIMDALL_CHILD_RUNNER_ENABLED`, `HEIMDALL_CHILD_ROOT_HOST`, and
  `HEIMDALL_CHILD_ROOT_CONTAINER`.
- `HEIMDALL_DATABASE_URL` supports only `sqlite:///...`.
- The API image listens on `8000` and expects its runtime directory at
  `/var/lib/heimdall`.
- The Web image serves nginx on `80`, bakes `VITE_API_BASE_URL` at build time,
  and does not proxy `/api`.
- A manual deploy with `dry_run=false` performs real local Dockerfile deploys.
- `build_env` values are passed as Docker build args. `runtime_env` values are
  passed as container environment variables.
- Preview containers do not receive generated bind mounts today.
- The API has a logical project-volume DB/read/write model; UI, YAML
  import/export, and executor bind-mount generation remain pending.
- Compose mode is unsupported and rejected.

Proposed storage contract:

- `HEIMDALL_VOLUME_ROOT_HOST` and `HEIMDALL_VOLUME_ROOT_CONTAINER` are optional
  settings, required only when API logical volumes are configured.
- Generated preview bind mounts are not implemented today and must not be
  required for current no-volume deploys.
- UI should collect a logical mount name, container target path, and `read_only`
  flag. Heimdall should generate the host source path under a managed
  `project-volumes` root.

Implemented nested child contract:

- The operator still starts and maintains the outer Heimdall manually.
- The outer UI can deploy the inner Heimdall API by exposing a per-service
  `Heimdall API child` control, stored as service-level
  `run_as_heimdall_child` with a project-level summary flag.
- The outer child runner is enabled only by server env:
  `HEIMDALL_CHILD_RUNNER_ENABLED=true`,
  `HEIMDALL_CHILD_ROOT_HOST`, and `HEIMDALL_CHILD_ROOT_CONTAINER`.
- Child roots use `{project_id}` as the fixed child ID:
  `{HEIMDALL_CHILD_ROOT_HOST}/{project_id}/runtime` and
  `{HEIMDALL_CHILD_ROOT_HOST}/{project_id}/project-volumes`.
- The implemented minimum slice is inner Heimdall API only. Multi-service
  projects can mark exactly one service as the child API service, but Heimdall
  does not automate inner Web lifecycle, child env files, or user preview
  volume mounts.

## Design Rules

- Each Heimdall process follows only its own environment and mount contract.
- An instance must not need to know whether it is depth 0, depth 1, or nested
  deeper.
- VM host paths and container paths must always be written separately.
- Runtime state and project application volumes are different storage classes.
- Docker bind mount source paths are resolved on the Docker daemon host VM, not
  inside the Heimdall API container.
- Mounting `/var/run/docker.sock` into Heimdall is a high-trust operation. It
  effectively gives Heimdall control of the VM Docker daemon.

## Outer And Inner Model

```text
VM host
  Docker daemon
  /var/run/docker.sock
  /srv/heimdall
    runtime/
    children/
      {project_id}/
        runtime/
        project-volumes/

Outer Heimdall API container
  /var/lib/heimdall -> /srv/heimdall/runtime
  /srv/heimdall/children -> /srv/heimdall/children (host-root validation)
  /host/children -> /srv/heimdall/children
  /var/run/docker.sock -> VM Docker daemon
  deploys and manages the inner Heimdall containers

Inner Heimdall API container
  /var/lib/heimdall -> /srv/heimdall/children/{project_id}/runtime
  /host/project-volumes -> /srv/heimdall/children/{project_id}/project-volumes
  /var/run/docker.sock -> same VM Docker daemon
  deploys and manages user project preview containers
```

The outer instance does not need special depth-aware code. From its point of
view, the inner Heimdall API is the one service marked with the
operator-approved `run_as_heimdall_child` flag. Existing single-service projects
use the project-level flag as a compatibility summary.
The inner instance also does not need special depth-aware code. It sees its own
runtime directory, own database, own preview port range, and the Docker daemon
socket provided by the operator.

## Canonical VM Layout

Use `/srv/heimdall` as the outer Heimdall root. Put nested Heimdall instances
under `children/`.

```text
/srv/heimdall/
  config/
    api.env
  runtime/
    state/
      heimdall.db
    logs/
      deployments/
    workspaces/
    secrets/
    env/
  children/
    {child_project_id}/
      runtime/
        state/
          heimdall.db
        logs/
          deployments/
        workspaces/
        secrets/
        env/
      project-volumes/
        {inner_project_id}/
          {service_id}/
            {volume_id}/
```

## Directory Creation Strategy

Current operating decision:

- The operator creates the outer root on the VM before running Heimdall.
- If the operator runs an inner Heimdall manually today, they may also create a
  named child root such as `heimdall-main`; that is a manual runbook example,
  not the planned outer-managed child ID model.
- Heimdall may create runtime subdirectories under mounted runtime roots, but
  it does not yet create child roots for nested API projects.

Create these VM paths for the outer instance during setup:

```text
/srv/heimdall/runtime
/srv/heimdall/children
```

Implemented child runner:

- The outer Heimdall API container mounts `/srv/heimdall/children` at
  `/host/children`.
- When a project has exactly one service stored with
  `run_as_heimdall_child=true`, the outer Heimdall creates or checks
  `/host/children/{project_id}/runtime` and
  `/host/children/{project_id}/project-volumes`.
- Docker daemon arguments still use VM host paths such as
  `/srv/heimdall/children/{project_id}/runtime`.
- The minimum slice does not create child env files or automate inner Web.

## Folder Roles

| VM path | Role | Container path | Backup policy |
| --- | --- | --- | --- |
| `/srv/heimdall/config` | Operator-owned env files and launch config for the outer instance. | Usually mounted as files or read by Docker run options. | Back up after redacting secrets where copies are shared. |
| `/srv/heimdall/runtime` | Outer Heimdall runtime root. | `/var/lib/heimdall` in the outer API container. | Back up for restore. |
| `/srv/heimdall/runtime/state` | SQLite database and durable API state. | `/var/lib/heimdall/state` | Back up before upgrades and deletes. |
| `/srv/heimdall/runtime/logs` | Deployment logs. | `/var/lib/heimdall/logs` | Back up if audit history matters. |
| `/srv/heimdall/runtime/workspaces` | Git workspaces used during deployment. | `/var/lib/heimdall/workspaces` | Disposable; can be repaired by refetching repos. |
| `/srv/heimdall/runtime/secrets` | Ignored runtime secret material when used by operators. | `/var/lib/heimdall/secrets` | Back up securely, never commit. |
| `/srv/heimdall/runtime/env` | Runtime env files generated or managed outside repo YAML. | `/var/lib/heimdall/env` | Back up securely if it contains operational values. |
| `/srv/heimdall/children` | Roots for nested Heimdall child API projects. | Planned outer API management path: `/host/children` | Back up per child instance. |
| `/srv/heimdall/children/{project_id}/runtime` | Inner Heimdall runtime root for a child API project. | `/var/lib/heimdall` in the inner API container. | Back up for inner restore. |
| `/srv/heimdall/children/{project_id}/project-volumes` | Project-volume root for projects managed by the inner instance. | `/host/project-volumes` in the inner API container. | Back up as application data. |
| `project-volumes/{inner_project_id}/{service_id}/{volume_id}` | Future host source directory for one generated project-volume mount. Logical names remain UI/display intent and must not determine physical placement. | Mounted into the user project container at its requested target path. | Delete only by explicit project/application data policy. |

## Environment Examples

The examples are split by implementation status. Put implemented API settings
in production `api.env` files today. Use the child-runner variables only on an
outer instance that should be allowed to deploy a child Heimdall API.

Current outer Heimdall API env:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_PUBLIC_BASE_URL=https://outer-heimdall.example.com
HEIMDALL_PREVIEW_HOST=127.0.0.1
HEIMDALL_PREVIEW_PORT_START=18000
HEIMDALL_PREVIEW_PORT_END=18999
HEIMDALL_GITHUB_API_TOKEN=...
HEIMDALL_GITHUB_WEBHOOK_SECRET=...
HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com
HEIMDALL_GITLAB_API_TOKEN=...
HEIMDALL_GITLAB_WEBHOOK_SECRET=...
```

Outer child-runner env for the implemented minimum slice:

```env
HEIMDALL_CHILD_RUNNER_ENABLED=true
HEIMDALL_CHILD_ROOT_HOST=/srv/heimdall/children
HEIMDALL_CHILD_ROOT_CONTAINER=/host/children
```

Current inner Heimdall API env:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_PUBLIC_BASE_URL=https://inner-heimdall.example.com
HEIMDALL_PREVIEW_HOST=127.0.0.1
HEIMDALL_PREVIEW_PORT_START=19000
HEIMDALL_PREVIEW_PORT_END=19999
HEIMDALL_GITHUB_API_TOKEN=...
HEIMDALL_GITHUB_WEBHOOK_SECRET=...
HEIMDALL_GITLAB_BASE_URL=https://gitlab.example.com
HEIMDALL_GITLAB_API_TOKEN=...
HEIMDALL_GITLAB_WEBHOOK_SECRET=...
```

Inner project-volume env for a child API project. The outer child runner
injects these values with Docker `--env` args in the minimum slice; generated
user preview bind mounts are still pending:

```env
HEIMDALL_VOLUME_ROOT_HOST=/srv/heimdall/children/{project_id}/project-volumes
HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes
```

Web image build env is separate from API `api.env` files:

```env
VITE_API_BASE_URL=https://inner-heimdall.example.com
```

`VITE_API_BASE_URL` is baked into the Web image at build time. Rebuild the Web
image when it changes.

`HEIMDALL_PREVIEW_HOST` is currently used in preview URLs and Docker port
publishing. Choose a value that matches the deployment topology. For local-only
or reverse-proxied previews, `127.0.0.1` can be appropriate. For directly
reachable previews, use a Docker-host address that the VM can bind and users can
reach.

`HEIMDALL_REPO_ROOT` is set to `/app` by the API Docker image. Do not override
it in normal Docker self-hosting.

## API Container Mount Examples

Outer API container:

```bash
docker run -d \
  --name heimdall-outer-api \
  --env-file /srv/heimdall/config/api.env \
  -p 8000:8000 \
  -v /srv/heimdall/runtime:/var/lib/heimdall \
  -v /srv/heimdall/children:/srv/heimdall/children:ro \
  -v /srv/heimdall/children:/host/children \
  -v /var/run/docker.sock:/var/run/docker.sock \
  heimdall-api:local
```

The `/host/children` mount is the contract for the child runner. The outer API
process creates or checks child directories through container paths such as:

```text
/host/children/{project_id}/runtime
/host/children/{project_id}/project-volumes
```

Docker daemon arguments are different. Because Docker bind mount sources and
paths are resolved on the VM host, the outer API must pass VM paths when it
asks Docker to run the child API:

```text
-v /srv/heimdall/children/{project_id}/runtime:/var/lib/heimdall
-v /srv/heimdall/children/{project_id}/project-volumes:/host/project-volumes
-v /var/run/docker.sock:/var/run/docker.sock
```

Child API env values are passed with Docker `--env` args, not a child env file:

```env
HEIMDALL_RUNTIME_DIR=/var/lib/heimdall
HEIMDALL_DATABASE_URL=sqlite:////var/lib/heimdall/state/heimdall.db
HEIMDALL_VOLUME_ROOT_HOST=/srv/heimdall/children/{project_id}/project-volumes
HEIMDALL_VOLUME_ROOT_CONTAINER=/host/project-volumes
```

For the current manual inner Heimdall fallback, use the operations runbook.
Manual examples may use a friendly name like `heimdall-main`; the
outer-managed child runner uses `{project_id}`.

## Host Root And Container Root Mapping

The future project-volume contract needs two roots because the Heimdall API
container and Docker daemon see paths from different namespaces.

```text
HEIMDALL_VOLUME_ROOT_HOST
= absolute directory on the VM host
= path passed to Docker as the bind mount source

HEIMDALL_VOLUME_ROOT_CONTAINER
= same storage as seen inside the Heimdall API container
= path the API process uses to create, inspect, and manage directories
```

For a generated physical relative source path:

```text
{project_id}/{service_id}/{volume_id}
```

Heimdall should translate it as:

```text
host source:
  {HEIMDALL_VOLUME_ROOT_HOST}/{project_id}/{service_id}/{volume_id}

API container management path:
  {HEIMDALL_VOLUME_ROOT_CONTAINER}/{project_id}/{service_id}/{volume_id}

project container target:
  user-declared absolute container path, for example /app/uploads
```

The UI/API logical volume name and service selection are stored separately as
user-facing intent. They can be renamed without moving the generated physical
source directory.

Example future generated Docker argument:

```text
--mount type=bind,src=/srv/heimdall/children/{child_project_id}/project-volumes/project_abc/service_def/volume_ghi,dst=/app/uploads
```

If `read_only=true`, the generated mount should include `readonly`.

## Future UI Model

The UI should not ask users for host paths. It should collect only:

- logical mount name, such as `uploads`
- service name, such as `api`
- container target path, such as `/app/uploads`
- `read_only`

Heimdall should derive the host source under `project-volumes` from immutable
project, service, and volume IDs; create it with a safe normalized path; and
store the generated mapping as operational state.

Repo YAML may later declare logical volume needs, but it must not contain VM host
paths, Docker socket paths, runtime roots, volume roots, or secret values.

## Docker Socket Trust Boundary

Mounting `/var/run/docker.sock` gives the Heimdall API process access to the VM
Docker daemon. A process with that access can create containers, mount host
paths into containers, publish ports, read container metadata, stop containers,
and often escalate to broad host control through Docker features.

Operational requirements:

- Mount the Docker socket only into Heimdall API containers that are trusted to
  control the VM Docker daemon.
- Do not mount the Docker socket into user project preview containers.
- Do not allow repo YAML or UI inputs to specify arbitrary host source paths.
- Do not allow repo YAML or UI inputs to provide child root paths. The only UI
  control is the per-service `Heimdall API child` flag, gated by server env and
  stored as `run_as_heimdall_child`.
- Treat `docker.sock` access as VM-level administrative trust, not a narrow
  container-management permission.
- Run untrusted user workloads on a separate VM or with a stronger isolation
  strategy before accepting multi-tenant use.
- Prefer firewall and reverse-proxy boundaries around API, Web, and preview
  ports.

## Backup And Delete Policy

Back up before upgrades:

- `config/`
- `runtime/state/`
- `runtime/logs/` if audit history matters
- `runtime/secrets/` and `runtime/env/` if used
- each child instance root under `children/`
- future `project-volumes/` application data

Usually disposable:

- `runtime/workspaces/`
- failed temporary build outputs
- preview containers that can be recreated from a release image or a new deploy

Project delete should be explicit about data loss:

- stop/remove only Heimdall-managed containers and networks for the project
- remove release metadata and logs according to retention policy
- delete future `project-volumes/{project_id}` only after an explicit
  application-data confirmation

Child Heimdall delete should be treated like deleting a full product instance:

- stop the child API/Web containers
- back up or intentionally remove the child `runtime/`
- back up or intentionally remove the child `project-volumes/`
- remove the child root under `children/` only after confirmation

## Current Gaps

- Child runner support is limited to exactly one inner Heimdall API service per
  project; inner Web lifecycle automation is not implemented.
- Preview containers do not receive generated bind mounts.
- Preview executors do not yet create generated user project-volume
  directories.
- The API model for logical project volumes exists; UI support is pending.
- There is no repo YAML parser/import flow for logical volumes.
- Compose mode is unsupported.
- The Web image does not proxy `/api`.
- The API currently supports only SQLite database URLs.

## Implementation Follow-ups

Track nested child deploy work in
[Nested Heimdall Child Deploy Implementation Plan](../implementation/trusted-heimdall-child-mode.md).
Track generated project-volume mounts in
[Docker Project Volume Support Implementation Plan](../implementation/docker-project-volume-support.md).

- Add child lifecycle, inner Web, or multi-service child orchestration only
  after the API-only slice is stable.
- Use the existing settings for `HEIMDALL_VOLUME_ROOT_HOST` and
  `HEIMDALL_VOLUME_ROOT_CONTAINER`.
- Continue validating both roots are absolute and mounted-storage consistency
  before executor use.
- Extend the project-volume model into UI/YAML flows.
- Reject host paths, relative target paths, path traversal, symlink escapes, and
  reserved Docker socket targets.
- Generate host source paths under `project-volumes`.
- Add executor support for `--mount type=bind`.
- Test root translation, mount generation, read-only mounts, delete behavior,
  and log redaction.
- Update the operations runbook after generated bind mounts are implemented.
