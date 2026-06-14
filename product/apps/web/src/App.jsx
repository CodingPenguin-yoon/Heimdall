import { useEffect, useMemo, useState } from "react";
import { api } from "./api";

const tabs = ["Projects", "Deployments", "Settings"];
const MAX_FORM_SERVICES = 4;
const DATABASE_RETRYABLE_STATUSES = new Set(["pending", "failed", "needs_repair"]);
const DATABASE_DISABLED_STATUSES = new Set(["disabled", "purged"]);
const DATABASE_PURGE_CONFIRMATION = "purge managed project database";
let serviceFormKeySequence = 0;

function nextServiceFormKey() {
  serviceFormKeySequence += 1;
  return `service-form-${serviceFormKeySequence}`;
}

function makeService(overrides = {}) {
  return {
    form_key: nextServiceFormKey(),
    name: "app",
    build_context_path: ".",
    dockerfile_path: "Dockerfile",
    container_port: "3000",
    public: true,
    health_check_path: "/",
    startup_order: "0",
    build_env_text: "",
    runtime_env_text: "",
    required_secrets_text: "",
    ...overrides,
  };
}

function defaultServices() {
  return [makeService()];
}

function makeEmptyForm() {
  return {
    name: "",
    project_type: "web",
    provider: "github",
    repo_url: "",
    default_branch: "main",
    tracked_branch: "main",
    deploy_mode: "dockerfile",
    build_context_path: ".",
    dockerfile_path: "Dockerfile",
    container_port: "3000",
    preview_port: "",
    health_check_path: "/",
    startup_timeout_seconds: "60",
    auto_deploy_enabled: true,
    database_required: false,
    database_type: "postgres",
    database_env_var: "DATABASE_URL",
    services: defaultServices(),
  };
}

function statusTone(status) {
  if (!status) return "neutral";
  const normalized = status.toLowerCase();
  if (normalized.includes("failed") || normalized.includes("error")) return "danger";
  if (
    normalized.includes("success") ||
    normalized.includes("registered") ||
    normalized.includes("valid") ||
    normalized === "healthy" ||
    normalized === "ready"
  ) {
    return "success";
  }
  if (
    normalized.includes("queued") ||
    normalized.includes("deploy") ||
    normalized.includes("run") ||
    normalized.includes("not_ready")
  ) {
    return "warning";
  }
  return "neutral";
}

function databaseStatusTone(status) {
  if (!status) return "neutral";
  if (["active", "purged"].includes(status)) return "success";
  if (["failed", "needs_repair", "purge_failed"].includes(status)) return "danger";
  if (["pending", "purging", "orphaned"].includes(status)) return "warning";
  return "neutral";
}

function databaseStatusLabel(status) {
  return String(status || "unknown").replace(/_/g, " ");
}

function databaseIsEnabled(database) {
  if (!database) return false;
  return !DATABASE_DISABLED_STATUSES.has(database.status);
}

function projectStatus(project) {
  return project?.last_deployment_status || project?.status || "unknown";
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function pluralize(count, singular, plural = `${singular}s`) {
  return count === 1 ? singular : plural;
}

function deployModeForServices(services) {
  return services.length > 1 ? "multi_service_dockerfile" : "dockerfile";
}

function serviceCountLabel(count) {
  return `${count} ${pluralize(count, "service")}`;
}

function serviceRoleLabel(service) {
  return service.public ? "Preview entry" : "Internal only";
}

function ensurePreviewEntry(services) {
  const serviceList = services.length ? services : defaultServices();
  const previewIndex = serviceList.findIndex((service) => service.public);
  const selectedIndex = previewIndex >= 0 ? previewIndex : 0;
  return serviceList.map((service, index) => ({
    ...service,
    public: index === selectedIndex,
  }));
}

function yamlScalar(value, fallback = "") {
  const normalized = String(value ?? "").trim() || fallback;
  if (!normalized) return "\"\"";
  if (
    /^[A-Za-z0-9_./:@-]+$/.test(normalized) &&
    !["true", "false", "null", "~"].includes(normalized.toLowerCase()) &&
    !/^[0-9-]/.test(normalized)
  ) {
    return normalized;
  }
  return JSON.stringify(normalized);
}

function yamlNumber(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? String(parsed) : String(fallback);
}

function parseKeyValueLines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .reduce((accumulator, line) => {
      const separatorIndex = line.indexOf("=");
      if (separatorIndex <= 0) return accumulator;
      const key = line.slice(0, separatorIndex).trim();
      const itemValue = line.slice(separatorIndex + 1).trim();
      if (key) accumulator[key] = itemValue;
      return accumulator;
    }, {});
}

function parseSecretNames(value) {
  return String(value || "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function managedDatabaseIntent(formState) {
  return {
    required: Boolean(formState.database_required),
    type: "postgres",
    env_var: String(formState.database_env_var || "DATABASE_URL").trim() || "DATABASE_URL",
  };
}

function serviceHasManagedDatabaseSecret(service, envVar) {
  return parseSecretNames(service.required_secrets_text).includes(envVar);
}

function looksSecretLike(key, value) {
  const keyPattern = /(^|_)(SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|API_KEY|ACCESS_KEY|JWT|DATABASE_URL|DB_PASSWORD|CREDENTIAL)(_|$)/i;
  const valuePattern = /(-----BEGIN|bearer\s+|secret|token|password|passwd|private[_ -]?key|api[_ -]?key|:\/\/[^/\s:@]+:[^@\s]+@)/i;
  return keyPattern.test(key) || valuePattern.test(value);
}

function yamlMapLines(map, indent) {
  const entries = Object.entries(map);
  return entries.map(([key, value]) => {
    const safeValue = looksSecretLike(key, value) ? "[redacted]" : value;
    return `${" ".repeat(indent)}${key}: ${yamlScalar(safeValue)}`;
  });
}

function servicePayload(service) {
  return {
    name: service.name,
    build_context_path: service.build_context_path,
    dockerfile_path: service.dockerfile_path,
    container_port: Number(service.container_port),
    public: Boolean(service.public),
    health_check_path: service.health_check_path || "/",
    startup_order: Number.parseInt(service.startup_order, 10) || 0,
    build_env: parseKeyValueLines(service.build_env_text),
    runtime_env: parseKeyValueLines(service.runtime_env_text),
    required_secrets: parseSecretNames(service.required_secrets_text),
  };
}

function envMapToText(values) {
  return Object.entries(values || {})
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
}

function serviceToForm(service, fallbackPublic = false) {
  return {
    form_key: nextServiceFormKey(),
    name: service.name || "",
    build_context_path: service.build_context_path || ".",
    dockerfile_path: service.dockerfile_path || "Dockerfile",
    container_port: String(service.container_port || 3000),
    public: Boolean(service.public ?? fallbackPublic),
    health_check_path: service.health_check_path || "/",
    startup_order: String(service.startup_order ?? 0),
    build_env_text: envMapToText(service.build_env),
    runtime_env_text: envMapToText(service.runtime_env),
    required_secrets_text: (service.required_secrets || []).join("\n"),
  };
}

function projectToForm(project) {
  const deployMode = project.deploy_mode || "dockerfile";
  const apiServices = Array.isArray(project.services) ? project.services : [];
  const services =
    deployMode === "multi_service_dockerfile" && apiServices.length
      ? apiServices.map((service) => serviceToForm(service))
      : [
          serviceToForm(
            {
              ...(apiServices[0] || {}),
              name: apiServices[0]?.name || "app",
              build_context_path: apiServices[0]?.build_context_path || project.build_context_path || ".",
              dockerfile_path: apiServices[0]?.dockerfile_path || project.dockerfile_path || "Dockerfile",
              container_port: apiServices[0]?.container_port || project.container_port || 3000,
              public: true,
              health_check_path: apiServices[0]?.health_check_path || project.health_check_path || "/",
              startup_order: apiServices[0]?.startup_order ?? 0,
            },
            true,
          ),
        ];
  const normalizedServices = ensurePreviewEntry(services);
  const previewService = normalizedServices.find((service) => service.public) || normalizedServices[0];
  const database = project.database || null;
  return {
    ...makeEmptyForm(),
    name: project.name || "",
    provider: project.provider || "github",
    repo_url: project.repo_url || "",
    default_branch: project.default_branch || project.tracked_branch || "main",
    tracked_branch: project.tracked_branch || "main",
    deploy_mode: deployMode,
    build_context_path: previewService.build_context_path || ".",
    dockerfile_path: previewService.dockerfile_path || "Dockerfile",
    container_port: String(previewService.container_port || 3000),
    preview_port: project.preview_port ? String(project.preview_port) : "",
    health_check_path: previewService.health_check_path || "/",
    auto_deploy_enabled: Boolean(project.auto_deploy_enabled),
    database_required: databaseIsEnabled(database),
    database_type: database?.type || "postgres",
    database_env_var: database?.env_var || "DATABASE_URL",
    services: normalizedServices,
  };
}

function projectPayloadFromForm(formState, existingProject = null) {
  const services = ensurePreviewEntry(formState.services);
  const deployMode = deployModeForServices(services);
  const previewService = services.find((service) => service.public) || services[0];
  const databaseIntent = managedDatabaseIntent(formState);
  const basePayload = {
    name: formState.name,
    provider: formState.provider,
    repo_url: formState.repo_url,
    default_branch: formState.default_branch || formState.tracked_branch || "main",
    tracked_branch: formState.tracked_branch,
    deploy_mode: deployMode,
    auto_deploy_enabled: formState.auto_deploy_enabled,
  };
  if (String(formState.preview_port || "").trim()) {
    basePayload.preview_port = Number(formState.preview_port);
  }
  if (databaseIntent.required) {
    basePayload.database = databaseIntent;
  } else if (existingProject?.database && !DATABASE_DISABLED_STATUSES.has(existingProject.database.status)) {
    basePayload.database = databaseIntent;
  }
  if (deployMode === "multi_service_dockerfile") {
    return {
      ...basePayload,
      services: services.map(servicePayload),
    };
  }
  return {
    ...basePayload,
    build_context_path: previewService.build_context_path,
    dockerfile_path: previewService.dockerfile_path,
    container_port: Number(previewService.container_port),
    health_check_path: previewService.health_check_path || "/",
  };
}

function buildProjectYaml(formState) {
  const services = ensurePreviewEntry(formState.services);
  const deployMode = deployModeForServices(services);
  const lines = [
    "version: 1",
    "",
    "project:",
    `  name: ${yamlScalar(formState.name, "sample-preview")}`,
    `  type: ${yamlScalar(formState.project_type, "web")}`,
    "",
    "source:",
    `  tracked_branch: ${yamlScalar(formState.tracked_branch, "main")}`,
    "",
    "deploy:",
    `  mode: ${yamlScalar(deployMode, "dockerfile")}`,
  ];
  if (formState.database_required) {
    const database = managedDatabaseIntent(formState);
    lines.push(
      "",
      "database:",
      `  required: ${database.required ? "true" : "false"}`,
      `  type: ${yamlScalar(database.type, "postgres")}`,
      `  env_var: ${yamlScalar(database.env_var, "DATABASE_URL")}`,
    );
  }
  lines.push("", "services:");
  services.forEach((service, index) => {
    const buildEnv = parseKeyValueLines(service.build_env_text);
    const runtimeEnv = parseKeyValueLines(service.runtime_env_text);
    const requiredSecrets = parseSecretNames(service.required_secrets_text);
    lines.push(
      `  ${yamlScalar(service.name, `service-${index + 1}`)}:`,
      `    build_context_path: ${yamlScalar(service.build_context_path, ".")}`,
      `    dockerfile_path: ${yamlScalar(service.dockerfile_path, "Dockerfile")}`,
      `    container_port: ${yamlNumber(service.container_port, 3000)}`,
      `    public: ${service.public ? "true" : "false"}`,
      `    health_check_path: ${yamlScalar(service.health_check_path, "/")}`,
      `    startup_order: ${yamlNumber(service.startup_order, 0)}`,
    );
    if (Object.keys(buildEnv).length) {
      lines.push("    build_env:", ...yamlMapLines(buildEnv, 6));
    } else {
      lines.push("    build_env: {}");
    }
    if (Object.keys(runtimeEnv).length) {
      lines.push("    runtime_env:", ...yamlMapLines(runtimeEnv, 6));
    } else {
      lines.push("    runtime_env: {}");
    }
    if (requiredSecrets.length) {
      lines.push("    required_secrets:");
      requiredSecrets.forEach((secret) => lines.push(`      - ${yamlScalar(secret)}`));
    } else {
      lines.push("    required_secrets: []");
    }
  });
  return lines.join("\n");
}

function App() {
  const [activeTab, setActiveTab] = useState("Projects");
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [projectDetail, setProjectDetail] = useState(null);
  const [deployments, setDeployments] = useState([]);
  const [releases, setReleases] = useState([]);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState(null);
  const [logContent, setLogContent] = useState("");
  const [form, setForm] = useState(() => makeEmptyForm());
  const [editingProjectId, setEditingProjectId] = useState(null);
  const [providerStatus, setProviderStatus] = useState(null);
  const [repoValidation, setRepoValidation] = useState(null);
  const [repoValidationError, setRepoValidationError] = useState("");
  const [providerBusy, setProviderBusy] = useState("");
  const [trackedBranchTouched, setTrackedBranchTouched] = useState(false);
  const [error, setError] = useState("");
  const [activity, setActivity] = useState("");

  const selectedProject = useMemo(() => {
    if (projectDetail?.id === selectedProjectId) return projectDetail;
    return projects.find((project) => project.id === selectedProjectId) || null;
  }, [projectDetail, projects, selectedProjectId]);
  const isEditingProject = Boolean(editingProjectId);

  const isProjectDetailLoading = Boolean(selectedProjectId && projectDetail?.id !== selectedProjectId);
  const projectYamlPreview = useMemo(() => buildProjectYaml(form), [form]);
  const selectedWebhookRegistration = selectedProject?.webhook_registration || null;
  const selectedProviderReadiness = selectedProject?.provider ? providerStatus?.providers?.[selectedProject.provider] : null;

  const summary = useMemo(() => {
    const inactivePreview = projects.filter((project) => !project.has_real_preview).length;
    const autoDeploy = projects.filter((project) => project.auto_deploy_enabled).length;
    const failing = projects.filter((project) => statusTone(projectStatus(project)) === "danger").length;
    const deploying = projects.filter((project) => statusTone(projectStatus(project)) === "warning").length;

    return { inactivePreview, autoDeploy, failing, deploying };
  }, [projects]);

  function updateForm(field, value) {
    if (field === "tracked_branch") setTrackedBranchTouched(true);
    if (field === "repo_url" || field === "provider") {
      setRepoValidation(null);
      setRepoValidationError("");
    }
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateService(index, field, value) {
    setForm((current) => ({
      ...current,
      services: current.services.map((service, serviceIndex) => {
        if (serviceIndex !== index) return service;
        return { ...service, [field]: value };
      }),
    }));
  }

  function addService() {
    setForm((current) => {
      if (current.services.length >= MAX_FORM_SERVICES) return current;
      return {
        ...current,
        services: ensurePreviewEntry([
          ...current.services,
          makeService({
            name: `service-${current.services.length + 1}`,
            public: false,
            startup_order: String((current.services.length + 1) * 10),
          }),
        ]),
      };
    });
  }

  function removeService(index) {
    setForm((current) => {
      const nextServices = current.services.filter((_, serviceIndex) => serviceIndex !== index);
      return { ...current, services: ensurePreviewEntry(nextServices) };
    });
  }

  function selectPreviewService(index) {
    setForm((current) => ({
      ...current,
      services: current.services.map((service, serviceIndex) => ({
        ...service,
        public: serviceIndex === index,
      })),
    }));
  }

  function resetProjectForm() {
    setForm(makeEmptyForm());
    setEditingProjectId(null);
    setTrackedBranchTouched(false);
    setRepoValidation(null);
    setRepoValidationError("");
  }

  function loadProjectIntoForm(project) {
    if (!project?.id) return;
    setForm(projectToForm(project));
    setEditingProjectId(project.id);
    setTrackedBranchTouched(true);
    setRepoValidation(null);
    setRepoValidationError("");
    setActiveTab("Settings");
    setActivity(`Editing ${project.name}.`);
  }

  function clearProjectRuntimeState() {
    setProjectDetail(null);
    setDeployments([]);
    setReleases([]);
    setSelectedDeploymentId(null);
    setLogContent("");
  }

  async function refreshProjects(nextSelectedId = selectedProjectId) {
    const data = await api.listProjects();
    setProjects(data);
    if (!nextSelectedId && data.length) {
      setSelectedProjectId(data[0].id);
      return data[0].id;
    }
    if (nextSelectedId && data.some((project) => project.id === nextSelectedId)) {
      setSelectedProjectId(nextSelectedId);
      return nextSelectedId;
    }
    if (data.length) {
      setSelectedProjectId(data[0].id);
      return data[0].id;
    }
    setSelectedProjectId(null);
    clearProjectRuntimeState();
    return null;
  }

  async function refreshProviderStatus() {
    const data = await api.getProviderStatus();
    setProviderStatus(data);
    return data;
  }

  async function fetchProjectBundle(projectId) {
    if (!projectId) return null;
    const [detail, projectDeployments, projectReleases] = await Promise.all([
      api.getProject(projectId),
      api.listProjectDeployments(projectId),
      api.listReleases(projectId),
    ]);
    return { detail, projectDeployments, projectReleases };
  }

  function applyProjectBundle(bundle) {
    if (!bundle) return;
    setProjectDetail(bundle.detail);
    setDeployments(bundle.projectDeployments);
    setReleases(bundle.projectReleases);
    if (bundle.projectDeployments.length) {
      setSelectedDeploymentId((currentDeploymentId) =>
        bundle.projectDeployments.some((deployment) => deployment.id === currentDeploymentId)
          ? currentDeploymentId
          : bundle.projectDeployments[0].id,
      );
      return;
    }
    setSelectedDeploymentId(null);
    setLogContent("");
  }

  async function loadProject(projectId) {
    const bundle = await fetchProjectBundle(projectId);
    applyProjectBundle(bundle);
  }

  useEffect(() => {
    refreshProjects().catch((caughtError) => setError(caughtError.message));
    refreshProviderStatus().catch((caughtError) => setError(caughtError.message));
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      clearProjectRuntimeState();
      return undefined;
    }

    let isCurrent = true;
    clearProjectRuntimeState();
    fetchProjectBundle(selectedProjectId)
      .then((bundle) => {
        if (isCurrent) applyProjectBundle(bundle);
      })
      .catch((caughtError) => {
        if (isCurrent) setError(caughtError.message);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedDeploymentId) {
      setLogContent("");
      return undefined;
    }

    let isCurrent = true;
    setLogContent("");
    api
      .getDeploymentLogs(selectedDeploymentId)
      .then((data) => {
        if (isCurrent) setLogContent(data.content || "");
      })
      .catch((caughtError) => {
        if (isCurrent) setError(caughtError.message);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedDeploymentId]);

  async function handleSaveProject(event) {
    event.preventDefault();
    setError("");
    setActivity(isEditingProject ? "Saving project..." : "Creating project...");
    try {
      const payload = projectPayloadFromForm(form, isEditingProject ? selectedProject : null);
      const saved = isEditingProject
        ? await api.updateProject(editingProjectId, payload)
        : await api.createProject(payload);
      resetProjectForm();
      await refreshProjects(saved.id);
      await loadProject(saved.id);
      setActiveTab("Projects");
      setActivity(`${isEditingProject ? "Saved" : "Created"} ${saved.name}.`);
    } catch (caughtError) {
      setError(caughtError.message);
      setActivity("");
    }
  }

  async function handleRetryProjectDatabase(project) {
    if (!project?.id || !project.database?.id) return;
    setError("");
    setActivity(`Retrying managed PostgreSQL for ${project.name}...`);
    try {
      const saved = await api.retryProjectDatabase(project.id);
      await refreshProjects(saved.id);
      await loadProject(saved.id);
      setActivity(`Managed PostgreSQL status is ${databaseStatusLabel(saved.database?.status)}.`);
    } catch (caughtError) {
      setError(caughtError.message);
      setActivity("");
    }
  }

  async function handlePurgeProjectDatabase(project) {
    if (!project?.id || !project.database?.id) return;
    const confirmation = window.prompt(`Type "${DATABASE_PURGE_CONFIRMATION}" to purge this managed PostgreSQL resource.`);
    if (confirmation !== DATABASE_PURGE_CONFIRMATION) return;
    setError("");
    setActivity(`Purging managed PostgreSQL for ${project.name}...`);
    try {
      const database = await api.purgeProjectDatabase(project.id, {
        database_id: project.database.id,
        confirmation,
      });
      await refreshProjects(project.id);
      await loadProject(project.id);
      setActivity(`Managed PostgreSQL status is ${databaseStatusLabel(database.status)}.`);
    } catch (caughtError) {
      setError(caughtError.message);
      setActivity("");
    }
  }

  async function handleValidateRepo() {
    setError("");
    setRepoValidation(null);
    setRepoValidationError("");
    if (!form.repo_url.trim()) {
      setRepoValidationError("Repository URL is required.");
      return;
    }
    setProviderBusy("validate-repo");
    setActivity("Validating provider repository access...");
    try {
      const result = await api.validateRepo({
        provider: form.provider,
        repo_url: form.repo_url,
      });
      setRepoValidation(result);
      setForm((current) => {
        const currentBranch = (current.tracked_branch || "").trim();
        const shouldPrefill =
          result.default_branch &&
          (!trackedBranchTouched || currentBranch === "" || currentBranch.toLowerCase() === "main");
        return {
          ...current,
          provider: result.provider || current.provider,
          default_branch: result.default_branch || current.default_branch,
          tracked_branch: shouldPrefill ? result.default_branch : current.tracked_branch,
        };
      });
      setActivity(result.message);
    } catch (caughtError) {
      setRepoValidationError(caughtError.message);
      setActivity("");
    } finally {
      setProviderBusy("");
    }
  }

  async function handleRegisterWebhook(project) {
    if (!project?.id) return;
    setError("");
    setProviderBusy(`register-webhook:${project.id}`);
    setActivity(`Registering webhook for ${project.name}...`);
    try {
      const result = await api.registerProjectWebhook(project.id);
      await refreshProviderStatus();
      await refreshProjects(project.id);
      await loadProject(project.id);
      setActivity(result.message);
    } catch (caughtError) {
      setError(caughtError.message);
      setActivity("");
    } finally {
      setProviderBusy("");
    }
  }

  async function handleDeploy(project) {
    if (!project?.id) return;
    setError("");
    setActivity(`Deploying preview for ${project.name}...`);
    try {
      const result = await api.deployProject(project.id, {
        ref: project.tracked_branch,
        trigger_type: "manual",
      });
      await refreshProjects(project.id);
      await loadProject(project.id);
      if (result?.deployment?.id) setSelectedDeploymentId(result.deployment.id);
      setActiveTab("Deployments");
      setActivity(`Preview deployment completed for ${project.name}.`);
    } catch (caughtError) {
      setError(caughtError.message);
      setActivity("");
    }
  }

  async function handleToggleAutoDeploy(project) {
    if (!project?.id) return;
    setError("");
    try {
      await api.updateProject(project.id, {
        auto_deploy_enabled: !project.auto_deploy_enabled,
      });
      await refreshProjects(project.id);
      await loadProject(project.id);
    } catch (caughtError) {
      setError(caughtError.message);
    }
  }

  async function handleDeleteProject(project) {
    if (!project?.id) return;
    if (!window.confirm(`Delete ${project.name}?`)) return;
    setError("");
    try {
      await api.deleteProject(project.id);
      const nextId = await refreshProjects(null);
      if (nextId) {
        await loadProject(nextId);
      }
    } catch (caughtError) {
      setError(caughtError.message);
    }
  }

  async function handleRollback(projectId, releaseId) {
    if (!projectId || !releaseId) return;
    setError("");
    setActivity("Requesting image rollback...");
    try {
      await api.rollbackProject(projectId, { release_id: releaseId });
    } catch (caughtError) {
      if (caughtError.status === 409 && caughtError.payload) {
        setActivity(caughtError.payload.message);
        await refreshProjects(projectId);
        await loadProject(projectId);
        if (caughtError.payload.deployment?.id) setSelectedDeploymentId(caughtError.payload.deployment.id);
        setActiveTab("Deployments");
        return;
      }
      setError(caughtError.message);
      setActivity("");
    }
  }

  const selectedProjectName = selectedProject?.name || "No project selected";

  return (
    <div className="app-shell">
      <header className="top-header">
        <div>
          <p className="eyebrow">Heimdall</p>
          <h1>Preview Deployment Console</h1>
        </div>
        <div className="header-meta">
          <span className="badge tone-success">Preview services</span>
          <span className="api-base">API base: {api.baseUrl}</span>
        </div>
      </header>

      <nav className="tab-bar" aria-label="Preview console sections">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            className={activeTab === tab ? "is-active" : ""}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      <section className="summary-strip" aria-label="Project summary">
        <div>
          <span>Projects</span>
          <strong>{projects.length}</strong>
        </div>
        <div>
          <span>No live preview</span>
          <strong>{summary.inactivePreview}</strong>
        </div>
        <div>
          <span>Auto deploy</span>
          <strong>{summary.autoDeploy}</strong>
        </div>
        <div>
          <span>Deploying</span>
          <strong>{summary.deploying}</strong>
        </div>
        <div>
          <span>Failing</span>
          <strong>{summary.failing}</strong>
        </div>
      </section>

      {error ? <div className="callout danger">{error}</div> : null}
      {activity ? <div className="callout info">{activity}</div> : null}

      {activeTab === "Projects" ? (
        <main className="tab-panel">
          <section className="panel">
            <div className="panel-title-row">
              <div>
                <h2>Projects</h2>
                <p className="muted">Table-first project list. Select a row to inspect and operate on it.</p>
              </div>
              <button
                type="button"
                className="primary-button"
                onClick={() => {
                  resetProjectForm();
                  setActiveTab("Settings");
                }}
              >
                Register project
              </button>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Project</th>
                    <th>Provider</th>
                    <th>Branch</th>
                    <th>Status</th>
                    <th>Preview target</th>
                    <th>Last deploy</th>
                    <th>Auto</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project) => (
                    <tr
                      key={project.id}
                      className={selectedProjectId === project.id ? "is-selected" : ""}
                      onClick={() => setSelectedProjectId(project.id)}
                    >
                      <td>
                        <strong>{project.name}</strong>
                        <div className="mono muted">{project.slug}</div>
                      </td>
                      <td>{project.provider}</td>
                      <td className="mono">{project.tracked_branch}</td>
                      <td>
                        <span className={`badge tone-${statusTone(projectStatus(project))}`}>{projectStatus(project)}</span>
                      </td>
                      <td>
                        <div className="mono">{project.preview_url}</div>
                        <div className="muted">
                          {project.has_real_preview ? "real preview active" : "no live preview"}
                        </div>
                      </td>
                      <td>{project.last_deployment_at ? formatDate(project.last_deployment_at) : "Never"}</td>
                      <td>{project.auto_deploy_enabled ? "On" : "Off"}</td>
                      <td>
                        <div className="button-row">
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeploy(project);
                            }}
                          >
                            Deploy preview
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleToggleAutoDeploy(project);
                            }}
                          >
                            Toggle auto
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!projects.length ? (
                    <tr>
                      <td colSpan="8" className="empty-state">
                        No projects registered.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <div className="detail-grid">
            <section className="panel">
              <div className="panel-title-row">
                <div>
                  <h2>Project Detail</h2>
                  <p className="muted">
                    {isProjectDetailLoading ? "Loading selected project detail..." : selectedProjectName}
                  </p>
                </div>
                {selectedProject ? (
                  <span className="badge tone-warning">
                    {selectedProject.has_real_preview ? "Real preview active" : "No live preview"}
                  </span>
                ) : null}
              </div>

              {selectedProject ? (
                <div className="stack detail-block">
                  <div className="detail-header">
                    <div className="detail-identity">
                      <h3 title={selectedProject.name}>{selectedProject.name}</h3>
                      <p className="mono muted truncate-line" title={selectedProject.repo_url}>
                        {selectedProject.repo_url}
                      </p>
                    </div>
                    <div className="button-row">
                      <button
                        type="button"
                        className="primary-button"
                        disabled={!selectedProject.id}
                        onClick={() => handleDeploy(selectedProject)}
                      >
                        Deploy preview
                      </button>
                      <button
                        type="button"
                        disabled={!selectedProject.id}
                        onClick={() => loadProjectIntoForm(selectedProject)}
                      >
                        Edit settings
                      </button>
                      <button
                        type="button"
                        disabled={
                          !selectedProject.id ||
                          providerBusy === `register-webhook:${selectedProject.id}` ||
                          providerStatus?.public_base_url_usable === false
                        }
                        onClick={() => handleRegisterWebhook(selectedProject)}
                      >
                        Register/reuse webhook
                      </button>
                      <button
                        type="button"
                        disabled={!selectedProject.id}
                        onClick={() => handleToggleAutoDeploy(selectedProject)}
                      >
                        {selectedProject.auto_deploy_enabled ? "Disable auto" : "Enable auto"}
                      </button>
                      <button
                        type="button"
                        className="danger-button"
                        disabled={!selectedProject.id}
                        onClick={() => handleDeleteProject(selectedProject)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="stats-grid">
                    <div>
                      <span className="muted">Tracked branch</span>
                      <strong className="mono">{selectedProject.tracked_branch}</strong>
                    </div>
                    <div>
                      <span className="muted">Services</span>
                      <strong>{serviceCountLabel(selectedProject.services?.length || 1)}</strong>
                    </div>
                    <div>
                      <span className="muted">Container port</span>
                      <strong className="mono">{selectedProject.container_port}</strong>
                    </div>
                    <div>
                      <span className="muted">Health check</span>
                      <strong className="mono">
                        {selectedProject.health_check_url || selectedProject.health_check_path || "(none)"}
                      </strong>
                    </div>
                    <div>
                      <span className="muted">Current commit</span>
                      <strong className="mono">{selectedProject.current_commit_sha || "No real active release"}</strong>
                    </div>
                    <div>
                      <span className="muted">Preview target</span>
                      <strong className="mono">{selectedProject.preview_url}</strong>
                    </div>
                    <div>
                      <span className="muted">Webhook</span>
                      <strong>
                        <span className={`badge tone-${statusTone(selectedWebhookRegistration?.status || "not_ready")}`}>
                          {selectedWebhookRegistration?.status || "not registered"}
                        </span>
                      </strong>
                    </div>
                  </div>

                  {selectedProject.database ? (
                    <div className="database-panel">
                      <div className="database-panel-header">
                        <div>
                          <span className="muted">Managed PostgreSQL</span>
                          <strong>
                            <span className={`badge tone-${databaseStatusTone(selectedProject.database.status)}`}>
                              {databaseStatusLabel(selectedProject.database.status)}
                            </span>
                          </strong>
                        </div>
                        <div className="button-row">
                          {DATABASE_RETRYABLE_STATUSES.has(selectedProject.database.status) ? (
                            <button type="button" onClick={() => handleRetryProjectDatabase(selectedProject)}>
                              Retry
                            </button>
                          ) : null}
                          {selectedProject.database.status !== "purged" ? (
                            <button
                              type="button"
                              className="danger-button"
                              onClick={() => handlePurgeProjectDatabase(selectedProject)}
                            >
                              Purge
                            </button>
                          ) : null}
                        </div>
                      </div>
                      <div className="database-meta-grid">
                        <div>
                          <span className="muted">Resource ID</span>
                          <strong className="mono">{selectedProject.database.id}</strong>
                        </div>
                        <div>
                          <span className="muted">Env var</span>
                          <strong className="mono">{selectedProject.database.env_var}</strong>
                        </div>
                        <div>
                          <span className="muted">App endpoint</span>
                          <strong className="mono">
                            {selectedProject.database.app_host}:{selectedProject.database.app_port}
                          </strong>
                        </div>
                        <div>
                          <span className="muted">Network</span>
                          <strong className="mono">{selectedProject.database.network_name}</strong>
                        </div>
                        <div>
                          <span className="muted">Retention</span>
                          <strong>{selectedProject.database.retention_policy}</strong>
                        </div>
                        <div>
                          <span className="muted">Provisioned</span>
                          <strong>{formatDate(selectedProject.database.provisioned_at)}</strong>
                        </div>
                        <div>
                          <span className="muted">Orphaned</span>
                          <strong>{formatDate(selectedProject.database.orphaned_at)}</strong>
                        </div>
                        <div>
                          <span className="muted">Last error</span>
                          <strong>{selectedProject.database.last_error || "-"}</strong>
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {selectedProject.services?.length ? (
                    <div className="table-wrap compact service-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Service</th>
                            <th>Preview role</th>
                            <th>Dockerfile</th>
                            <th>Port</th>
                            <th>Health</th>
                            {selectedProject.database ? <th>DB env</th> : null}
                          </tr>
                        </thead>
                        <tbody>
                          {selectedProject.services.map((service) => (
                            <tr key={service.name}>
                              <td className="mono">{service.name}</td>
                              <td>{serviceRoleLabel(service)}</td>
                              <td className="mono truncate-cell" title={service.dockerfile_path}>
                                {service.dockerfile_path}
                              </td>
                              <td className="mono">{service.container_port}</td>
                              <td className="mono">{service.health_check_path || "/"}</td>
                              {selectedProject.database ? (
                                <td>
                                  <span
                                    className={`badge tone-${
                                      service.required_secrets?.includes(selectedProject.database.env_var)
                                        ? "success"
                                        : "neutral"
                                    }`}
                                  >
                                    {service.required_secrets?.includes(selectedProject.database.env_var)
                                      ? `${selectedProject.database.env_var} bound`
                                      : "not bound"}
                                  </span>
                                </td>
                              ) : null}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : null}

                  <div className="callout warning">
                    Manual deploy replaces the current Heimdall-managed preview container before starting the new one.
                    A failed replacement can leave the preview unavailable.
                  </div>
                  {providerStatus?.public_base_url_usable === false ? (
                    <div className="callout warning">
                      {providerStatus.public_base_url_message} Callback URL:{" "}
                      <span className="mono">
                        {providerStatus.webhook_urls?.[selectedProject.provider] || "(unavailable)"}
                      </span>
                    </div>
                  ) : null}
                  {selectedProviderReadiness && !selectedProviderReadiness.can_register_webhook ? (
                    <div className="callout warning">{selectedProviderReadiness.message}</div>
                  ) : null}
                  {selectedWebhookRegistration ? (
                    <div className="callout info">
                      {selectedWebhookRegistration.message}{" "}
                      <span className="mono">{selectedWebhookRegistration.webhook_url}</span>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="empty-state">Select a project to inspect deployments, releases, and logs.</div>
              )}
            </section>

            <section className="panel">
              <div className="panel-title-row">
                <div>
                  <h2>Releases / Rollback</h2>
                  <p className="muted">
                    Image rollback changes preview containers only; managed PostgreSQL data is not restored.
                  </p>
                </div>
              </div>
              {selectedProject?.database && databaseIsEnabled(selectedProject.database) ? (
                <div className="callout warning">
                  This project has a managed PostgreSQL binding. Rollback does not restore database data.
                </div>
              ) : null}
              <div className="table-wrap compact releases-table">
                <table>
                  <thead>
                    <tr>
                      <th>Commit</th>
                      <th>Image tag</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {releases.map((release) => (
                      <tr key={release.id}>
                        <td className="mono">{release.short_commit_sha}</td>
                        <td className="mono truncate-cell" title={release.image_tag}>
                          {release.services?.length ? (
                            <div className="release-service-list">
                              {release.services.map((service) => (
                                <div key={service.name}>
                                  <strong>{service.name}</strong>{" "}
                                  <span className={`badge tone-${service.public ? "success" : "neutral"}`}>
                                    {serviceRoleLabel(service)}
                                  </span>
                                  <span className={`badge tone-${statusTone(service.status)}`}>{service.status}</span>
                                  <span title={service.image_tag}>{service.image_tag}</span>
                                  <small>{service.public ? service.preview_url : service.internal_url}</small>
                                </div>
                              ))}
                            </div>
                          ) : (
                            release.image_tag
                          )}
                        </td>
                        <td>
                          <span className={`badge tone-${statusTone(release.status)}`}>{release.status}</span>
                        </td>
                        <td>{formatDate(release.created_at)}</td>
                        <td>
                          <button
                            type="button"
                            disabled={!selectedProject?.id}
                            onClick={() => handleRollback(selectedProject?.id, release.id)}
                          >
                            Rollback image
                          </button>
                        </td>
                      </tr>
                    ))}
                    {!releases.length ? (
                      <tr>
                        <td colSpan="5" className="empty-state">
                          No releases recorded yet.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </main>
      ) : null}

      {activeTab === "Deployments" ? (
        <main className="tab-panel">
          <div className="context-row">
            <div>
              <span className="muted">Selected project</span>
              <strong>{selectedProjectName}</strong>
            </div>
            <div>
              <span className="muted">Deployments</span>
              <strong>
                {deployments.length} {pluralize(deployments.length, "record")}
              </strong>
            </div>
            <button
              type="button"
              className="primary-button"
              disabled={!selectedProject?.id}
              onClick={() => handleDeploy(selectedProject)}
            >
              Deploy preview
            </button>
          </div>

          <div className="detail-grid deployments-grid">
            <section className="panel">
              <div className="panel-title-row">
                <div>
                  <h2>Deployment History</h2>
                  <p className="muted">Newest first for the selected project.</p>
                </div>
              </div>
              <div className="table-wrap compact">
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Trigger</th>
                      <th>Commit</th>
                      <th>Image tag</th>
                      <th>Started</th>
                      <th>Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deployments.map((deployment) => (
                      <tr
                        key={deployment.id}
                        className={selectedDeploymentId === deployment.id ? "is-selected" : ""}
                        onClick={() => setSelectedDeploymentId(deployment.id)}
                      >
                        <td>
                          <span className={`badge tone-${statusTone(deployment.status)}`}>{deployment.status}</span>
                        </td>
                        <td>{deployment.trigger_type}</td>
                        <td className="mono">
                          {deployment.resolved_commit_sha?.slice(0, 12) || deployment.requested_ref || "-"}
                        </td>
                        <td className="mono">{deployment.image_tag || "-"}</td>
                        <td>{formatDate(deployment.started_at || deployment.created_at)}</td>
                        <td>{deployment.duration_ms != null ? `${deployment.duration_ms}ms` : "-"}</td>
                      </tr>
                    ))}
                    {!deployments.length ? (
                      <tr>
                        <td colSpan="6" className="empty-state">
                          No deployments recorded for this project.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="panel">
              <div className="panel-title-row">
                <div>
                  <h2>Logs</h2>
                  <p className="muted">Sectioned executor output for the selected deployment.</p>
                </div>
                <span className="mono small-text">{selectedDeploymentId || "No deployment selected"}</span>
              </div>
              <pre className="log-panel">{logContent || "No log output available."}</pre>
            </section>
          </div>
        </main>
      ) : null}

      {activeTab === "Settings" ? (
        <main className="tab-panel settings-grid">
          <form className="panel stack" onSubmit={handleSaveProject}>
            <div className="panel-title-row">
              <div>
                <h2>{isEditingProject ? "Edit Project" : "Register Project"}</h2>
                <p className="muted">
                  {isEditingProject
                    ? "Save project settings, then review the repo-safe YAML preview."
                    : "Save a project into Heimdall, then review the repo-safe YAML preview."}
                </p>
              </div>
              <span className="badge tone-warning">
                {isEditingProject ? selectedProject?.name || "Editing" : serviceCountLabel(form.services.length)}
              </span>
            </div>

            <fieldset>
              <legend>Source</legend>
              <div className="split-fields">
                <label>
                  <span>Name</span>
                  <input value={form.name} onChange={(event) => updateForm("name", event.target.value)} required />
                </label>
                <label>
                  <span>Project type</span>
                  <select value={form.project_type} onChange={(event) => updateForm("project_type", event.target.value)}>
                    <option value="web">Web</option>
                    <option value="worker">Worker</option>
                    <option value="service">Service</option>
                  </select>
                </label>
              </div>

              <div className="split-fields">
                <label>
                  <span>Provider</span>
                  <select value={form.provider} onChange={(event) => updateForm("provider", event.target.value)}>
                    <option value="github">GitHub</option>
                    <option value="gitlab">GitLab</option>
                  </select>
                </label>
                <label>
                  <span>Tracked branch</span>
                  <input
                    value={form.tracked_branch}
                    onChange={(event) => updateForm("tracked_branch", event.target.value)}
                    required
                  />
                </label>
              </div>

              <div className="field-action-row">
                <label>
                  <span>Repository URL</span>
                  <input
                    value={form.repo_url}
                    onChange={(event) => updateForm("repo_url", event.target.value)}
                    placeholder="https://github.com/org/repo.git"
                    required
                  />
                </label>
                <button
                  type="button"
                  disabled={providerBusy === "validate-repo" || !form.repo_url.trim()}
                  onClick={handleValidateRepo}
                >
                  Validate access
                </button>
              </div>
              {repoValidation ? (
                <div className="validation-result">
                  <div>
                    <span className="muted">Access</span>
                    <strong>
                      <span className="badge tone-success">valid</span>
                    </strong>
                  </div>
                  <div>
                    <span className="muted">Default branch</span>
                    <strong className="mono">{repoValidation.default_branch || "-"}</strong>
                  </div>
                  <div>
                    <span className="muted">Visibility</span>
                    <strong>{repoValidation.private ? "Private" : "Public"}</strong>
                  </div>
                  <div>
                    <span className="muted">Webhook</span>
                    <strong>
                      <span className={`badge tone-${repoValidation.can_register_webhook ? "success" : "warning"}`}>
                        {repoValidation.can_register_webhook ? "ready" : "not ready"}
                      </span>
                    </strong>
                  </div>
                  <div className="validation-wide">
                    <span className="muted">Repository</span>
                    <strong className="mono">{repoValidation.full_name}</strong>
                  </div>
                </div>
              ) : null}
              {repoValidationError ? <div className="callout danger">{repoValidationError}</div> : null}
            </fieldset>

            <fieldset>
              <legend>Build</legend>
              <div className="service-editor">
                <div className="button-row">
                  <button type="button" disabled={form.services.length >= MAX_FORM_SERVICES} onClick={addService}>
                    + Add service
                  </button>
                  <span className="badge tone-neutral">{serviceCountLabel(form.services.length)}</span>
                </div>
                {form.services.map((service, index) => (
                  <div className="service-row" key={service.form_key || `service-form-${index}`}>
                    <div className="service-row-title">
                      <strong>{service.name || `service-${index + 1}`}</strong>
                      <div className="service-row-title-actions">
                        <label className="switch-line">
                          <input
                            type="radio"
                            name="preview-entry-service"
                            checked={service.public}
                            onChange={() => selectPreviewService(index)}
                          />
                          <span>Preview entry</span>
                        </label>
                        <span className={`badge tone-${service.public ? "success" : "neutral"}`}>
                          {serviceRoleLabel(service)}
                        </span>
                      </div>
                    </div>
                    {form.services.length > 1 ? (
                      <div className="split-fields">
                        <label>
                          <span>Name</span>
                          <input
                            value={service.name}
                            onChange={(event) => updateService(index, "name", event.target.value)}
                            required
                          />
                        </label>
                        <label>
                          <span>Startup order</span>
                          <input
                            type="number"
                            value={service.startup_order}
                            onChange={(event) => updateService(index, "startup_order", event.target.value)}
                          />
                        </label>
                      </div>
                    ) : null}
                    <div className="split-fields">
                      <label>
                        <span>Build context</span>
                        <input
                          value={service.build_context_path}
                          onChange={(event) => updateService(index, "build_context_path", event.target.value)}
                          required
                        />
                      </label>
                      <label>
                        <span>Dockerfile path</span>
                        <input
                          value={service.dockerfile_path}
                          onChange={(event) => updateService(index, "dockerfile_path", event.target.value)}
                          required
                        />
                      </label>
                    </div>
                    <div className="split-fields">
                      <label>
                        <span>Container port</span>
                        <input
                          type="number"
                          value={service.container_port}
                          onChange={(event) => updateService(index, "container_port", event.target.value)}
                          min="1"
                          max="65535"
                          required
                        />
                      </label>
                      <label>
                        <span>Health path</span>
                        <input
                          value={service.health_check_path}
                          onChange={(event) => updateService(index, "health_check_path", event.target.value)}
                          placeholder="/health"
                        />
                      </label>
                    </div>
                    {form.services.length > 1 ? (
                      <>
                        <div className="split-fields">
                          <label>
                            <span>Build env</span>
                            <textarea
                              value={service.build_env_text}
                              onChange={(event) => updateService(index, "build_env_text", event.target.value)}
                              rows="3"
                              placeholder="VITE_API_BASE_URL=/api"
                            />
                          </label>
                          <label>
                            <span>Runtime env</span>
                            <textarea
                              value={service.runtime_env_text}
                              onChange={(event) => updateService(index, "runtime_env_text", event.target.value)}
                              rows="3"
                              placeholder="PORT=8000"
                            />
                          </label>
                        </div>
                        <label>
                          <span>Required secret names</span>
                          <textarea
                            value={service.required_secrets_text}
                            onChange={(event) => updateService(index, "required_secrets_text", event.target.value)}
                            rows="2"
                            placeholder="DATABASE_URL"
                          />
                        </label>
                      </>
                    ) : null}
                    <div className="button-row">
                      <button type="button" disabled={form.services.length <= 1} onClick={() => removeService(index)}>
                        Remove service
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </fieldset>

            <fieldset>
              <legend>Runtime</legend>
              <div className="split-fields">
                <label>
                  <span>Preview port</span>
                  <input
                    type="number"
                    value={form.preview_port}
                    onChange={(event) => updateForm("preview_port", event.target.value)}
                    min="1"
                    max="65535"
                    placeholder="auto"
                  />
                </label>
                <label>
                  <span>Startup timeout</span>
                  <input
                    type="number"
                    value={form.startup_timeout_seconds}
                    onChange={(event) => updateForm("startup_timeout_seconds", event.target.value)}
                    min="1"
                    max="600"
                  />
                </label>
              </div>
              <div className="database-form-block">
                <label className="switch-line">
                  <input
                    type="checkbox"
                    checked={form.database_required}
                    onChange={(event) => updateForm("database_required", event.target.checked)}
                  />
                  <span>Managed PostgreSQL</span>
                </label>
                {form.database_required ? (
                  <>
                    <div className="split-fields">
                      <label>
                        <span>Type</span>
                        <select
                          value={form.database_type}
                          onChange={(event) => updateForm("database_type", event.target.value)}
                          disabled
                        >
                          <option value="postgres">Postgres</option>
                        </select>
                      </label>
                      <label>
                        <span>Env var</span>
                        <input
                          value={form.database_env_var}
                          onChange={(event) => updateForm("database_env_var", event.target.value)}
                          pattern="[A-Z_][A-Z0-9_]*"
                          maxLength="63"
                        />
                      </label>
                    </div>
                    {form.services.length > 1 ? (
                      <div className="database-binding-list">
                        {form.services.map((service) => {
                          const isBound = serviceHasManagedDatabaseSecret(service, managedDatabaseIntent(form).env_var);
                          return (
                            <span
                              key={service.form_key || service.name}
                              className={`badge tone-${isBound ? "success" : "neutral"}`}
                            >
                              {service.name || "service"}: {isBound ? "DB env bound" : "not bound"}
                            </span>
                          );
                        })}
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            </fieldset>

            <fieldset>
              <legend>Automation</legend>
              <label className="switch-line">
                <input
                  type="checkbox"
                  checked={form.auto_deploy_enabled}
                  onChange={(event) => updateForm("auto_deploy_enabled", event.target.checked)}
                />
                <span>Enable auto deploy</span>
              </label>
            </fieldset>

            <div className="button-row">
              <button type="submit" className="primary-button">
                {isEditingProject ? "Save Changes" : "Create Project"}
              </button>
              {isEditingProject ? (
                <button type="button" onClick={resetProjectForm}>
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>

          <div className="settings-side stack">
            <section className="panel provider-panel">
              <div className="panel-title-row">
                <div>
                  <h2>Provider Readiness</h2>
                  <p className="muted">Configured status for validation and webhook registration.</p>
                </div>
                <span className={`badge tone-${providerStatus?.public_base_url_usable ? "success" : "warning"}`}>
                  {providerStatus?.public_base_url_usable ? "public url ready" : "public url local"}
                </span>
              </div>
              <div className="readiness-grid">
                <div className="readiness-wide">
                  <span className="muted">Public base URL</span>
                  <strong className="mono">{providerStatus?.public_base_url || "Loading..."}</strong>
                  <small>{providerStatus?.public_base_url_message || ""}</small>
                </div>
                <div>
                  <span className="muted">GitHub token</span>
                  <strong>
                    <span
                      className={`badge tone-${providerStatus?.providers?.github?.token_configured ? "success" : "warning"}`}
                    >
                      {providerStatus?.providers?.github?.token_configured ? "configured" : "missing"}
                    </span>
                  </strong>
                </div>
                <div>
                  <span className="muted">GitHub secret</span>
                  <strong>
                    <span
                      className={`badge tone-${
                        providerStatus?.providers?.github?.webhook_secret_configured ? "success" : "warning"
                      }`}
                    >
                      {providerStatus?.providers?.github?.webhook_secret_configured ? "configured" : "missing"}
                    </span>
                  </strong>
                </div>
                <div>
                  <span className="muted">GitLab base URL</span>
                  <strong className="mono">{providerStatus?.providers?.gitlab?.base_url || "missing"}</strong>
                </div>
                <div>
                  <span className="muted">GitLab token</span>
                  <strong>
                    <span
                      className={`badge tone-${providerStatus?.providers?.gitlab?.token_configured ? "success" : "warning"}`}
                    >
                      {providerStatus?.providers?.gitlab?.token_configured ? "configured" : "missing"}
                    </span>
                  </strong>
                </div>
                <div>
                  <span className="muted">GitLab secret</span>
                  <strong>
                    <span
                      className={`badge tone-${
                        providerStatus?.providers?.gitlab?.webhook_secret_configured ? "success" : "warning"
                      }`}
                    >
                      {providerStatus?.providers?.gitlab?.webhook_secret_configured ? "configured" : "missing"}
                    </span>
                  </strong>
                </div>
              </div>
            </section>

            <section className="panel yaml-panel">
              <div className="panel-title-row">
                <div>
                  <h2>.heimdall/project.yaml</h2>
                  <p className="muted">Repo-safe preview generated from the current form values.</p>
                </div>
                <span className="badge tone-neutral">Preview</span>
              </div>
              <pre className="yaml-preview">{projectYamlPreview}</pre>
            </section>
          </div>
        </main>
      ) : null}
    </div>
  );
}

export default App;
