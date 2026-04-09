from __future__ import annotations

import re
from pathlib import Path

import httpx

from src.models.baseline import (
    APIEndpoint,
    BaselineDocument,
    CIConfig,
    CommunicationLink,
    ConsumedAPI,
    DataStore,
    ExternalRef,
    ServiceInventoryEntry,
    TechStack,
)
from src.services.git_ops import GitOps

# --- Source File Scanner (T004) ---

CONTROLLER_PATTERN = re.compile(
    r'@(?:Rest)?Controller\b.*?class\s+(\w+)', re.DOTALL
)
REQUEST_MAPPING_PATTERN = re.compile(
    r'@(?:Request|Get|Post|Put|Delete|Patch)Mapping\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']',
)
ENTITY_PATTERN = re.compile(
    r'@Entity\b.*?class\s+(\w+)', re.DOTALL
)
TABLE_PATTERN = re.compile(
    r'@Table\(\s*name\s*=\s*["\'](\w+)["\']',
)


def scan_java_source(repo_dir: Path) -> dict:
    endpoints: list[APIEndpoint] = []
    entities: list[str] = []
    current_controller = ""
    base_path = ""

    java_files = list(repo_dir.rglob("*.java"))

    for java_file in java_files:
        try:
            content = java_file.read_text(errors="ignore")
        except OSError:
            continue

        controller_match = CONTROLLER_PATTERN.search(content)
        if controller_match:
            current_controller = controller_match.group(1)
            base_mapping = re.search(
                r'@RequestMapping\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']', content
            )
            base_path = base_mapping.group(1) if base_mapping else ""

            for match in REQUEST_MAPPING_PATTERN.finditer(content):
                method = "GET"
                annotation_match = re.search(
                    r'@(Get|Post|Put|Delete|Patch)Mapping', content[:match.start()][-100:]
                )
                if annotation_match:
                    method = annotation_match.group(1).upper()
                elif "@PostMapping" in content[max(0, match.start()-30):match.start()]:
                    method = "POST"

                path = base_path + match.group(1) if not match.group(1).startswith("/") else match.group(1)
                if not path.startswith("/"):
                    path = "/" + path

                request_dto = None
                response_dto = None
                body_match = re.search(
                    r'@RequestBody\s+(\w+)', content[match.end():match.end()+200]
                )
                if body_match:
                    request_dto = body_match.group(1)

                endpoints.append(APIEndpoint(
                    method=method,
                    path=path,
                    controller_class=current_controller,
                    request_dto=request_dto,
                    response_dto=response_dto,
                ))

        entity_match = ENTITY_PATTERN.search(content)
        if entity_match:
            entities.append(entity_match.group(1))

    return {"endpoints": endpoints, "entities": entities}


# --- Build File Scanner (T005) ---

def scan_build_files(repo_dir: Path) -> TechStack:
    tech = TechStack()

    gradle_file = repo_dir / "build.gradle.kts"
    if not gradle_file.exists():
        gradle_file = repo_dir / "build.gradle"

    if gradle_file.exists():
        content = gradle_file.read_text(errors="ignore")
        tech.build_tool = "Gradle"

        java_version = re.search(r'JavaVersion\.VERSION_(\d+)', content)
        if java_version:
            tech.language = f"Java {java_version.group(1)}"

        spring_version = re.search(r'"org\.springframework\.boot"\)\s*version\s*"([^"]+)"', content)
        if spring_version:
            tech.framework = f"Spring Boot {spring_version.group(1)}"

        deps = re.findall(r'(?:implementation|runtimeOnly|testImplementation)\("([^"]+)"\)', content)
        tech.key_dependencies = [d.split(":")[-1] if ":" in d else d for d in deps[:10]]

    pom_file = repo_dir / "pom.xml"
    if pom_file.exists() and not tech.build_tool:
        tech.build_tool = "Maven"
        content = pom_file.read_text(errors="ignore")
        java_match = re.search(r'<java\.version>(\d+)</java\.version>', content)
        if java_match:
            tech.language = f"Java {java_match.group(1)}"

    return tech


def scan_ci_config(repo_dir: Path) -> CIConfig | None:
    # Check GitLab CI first, then GitHub Actions
    ci_file = repo_dir / ".gitlab-ci.yml"
    if not ci_file.exists():
        workflows_dir = repo_dir / ".github" / "workflows"
        if workflows_dir.is_dir():
            wf_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            if wf_files:
                ci_file = wf_files[0]
    if not ci_file.exists():
        return None

    content = ci_file.read_text(errors="ignore")
    stages = re.findall(r'^\s+-\s+(\w+)', content, re.MULTILINE)
    image_match = re.search(r'image:\s+(.+)', content)
    commands = re.findall(r'script:\s*\n\s+-\s+(.+)', content)

    return CIConfig(
        stages=stages[:10],
        image=image_match.group(1).strip() if image_match else "",
        key_commands=commands[:5],
    )


def scan_data_stores(repo_dir: Path) -> list[DataStore]:
    stores: list[DataStore] = []
    app_yml = repo_dir / "src" / "main" / "resources" / "application.yml"
    if not app_yml.exists():
        app_yml = repo_dir / "src" / "main" / "resources" / "application.yaml"

    if app_yml.exists():
        content = app_yml.read_text(errors="ignore")
        url_match = re.search(r'url:\s*jdbc:(\w+):(\w+):(\w+)', content)
        if url_match:
            db_tech = url_match.group(1).upper()
            db_name = url_match.group(3)
            source_scan = scan_java_source(repo_dir)
            stores.append(DataStore(
                name=db_name,
                technology=db_tech,
                entities=source_scan.get("entities", []),
                config_source=str(app_yml.relative_to(repo_dir)),
            ))

    return stores


# --- Inter-Service Communication Detector (T006) ---

REST_TEMPLATE_PATTERN = re.compile(r'restTemplate\.\w+\(\s*["\']?([^"\')\s]+)')
FEIGN_PATTERN = re.compile(r'@FeignClient\(\s*(?:name\s*=\s*)?["\'](\w+)["\']')
SERVICE_URL_PATTERN = re.compile(r'\$\{([^}]*(?:service|url)[^}]*)\}', re.IGNORECASE)
CONFIG_URL_PATTERN = re.compile(r'(\w+):\s*\n\s*(?:service:)?\s*\n?\s*url:\s*(https?://[^\s]+)')


def scan_inter_service_calls(repo_dir: Path) -> list[ConsumedAPI]:
    consumed: list[ConsumedAPI] = []

    for java_file in repo_dir.rglob("*.java"):
        try:
            content = java_file.read_text(errors="ignore")
        except OSError:
            continue

        class_match = re.search(r'class\s+(\w+)', content)
        class_name = class_match.group(1) if class_match else java_file.stem

        for match in REST_TEMPLATE_PATTERN.finditer(content):
            consumed.append(ConsumedAPI(
                target_service="unknown",
                url_pattern=match.group(1)[:100],
                client_class=class_name,
                protocol="REST",
            ))

        for match in FEIGN_PATTERN.finditer(content):
            consumed.append(ConsumedAPI(
                target_service=match.group(1),
                url_pattern=f"@FeignClient({match.group(1)})",
                client_class=class_name,
                protocol="Feign",
            ))

    app_yml = repo_dir / "src" / "main" / "resources" / "application.yml"
    if app_yml.exists():
        content = app_yml.read_text(errors="ignore")
        for match in re.finditer(r'(\w+):\s*\n\s*service:\s*\n\s*url:\s*(https?://[^\s]+)', content):
            consumed.append(ConsumedAPI(
                target_service=match.group(1),
                url_pattern=match.group(2),
                client_class="config",
                protocol="REST",
            ))
        for match in re.finditer(r'url:\s*(https?://localhost:\d+[^\s]*)', content):
            consumed.append(ConsumedAPI(
                target_service="localhost service",
                url_pattern=match.group(1),
                client_class="config",
                protocol="REST",
            ))

    return consumed


# --- External Reference Extractor (T007) ---

URL_PATTERN = re.compile(r'https?://(?!localhost)[^\s"\'<>]+')
JIRA_PATTERN = re.compile(r'[A-Z]{2,10}-\d+')


def scan_external_references(repo_dir: Path) -> list[ExternalRef]:
    refs: list[ExternalRef] = []
    seen_urls: set[str] = set()

    scan_files = list(repo_dir.rglob("*.java")) + list(repo_dir.rglob("*.yml")) + list(repo_dir.rglob("*.md"))

    for f in scan_files[:100]:
        try:
            content = f.read_text(errors="ignore")
        except OSError:
            continue

        for match in URL_PATTERN.finditer(content):
            url = match.group(0).rstrip(".,;:)")
            if url not in seen_urls and "gradle.org" not in url and "springframework" not in url:
                seen_urls.add(url)
                fetched = None
                try:
                    resp = httpx.get(url, timeout=5.0, follow_redirects=True)
                    if resp.status_code == 200:
                        fetched = resp.text[:500]
                except Exception:
                    pass

                refs.append(ExternalRef(
                    url=url,
                    source_file=str(f.relative_to(repo_dir)),
                    context=content[max(0, match.start()-50):match.end()+50][:150],
                    fetched_content=fetched,
                ))

    return refs


# --- Multi-Repo Orchestrator (T008) ---

def scan_single_repo(repo_dir: Path, repo_path: str) -> ServiceInventoryEntry:
    source_scan = scan_java_source(repo_dir)
    tech_stack = scan_build_files(repo_dir)
    ci_config = scan_ci_config(repo_dir)
    data_stores = scan_data_stores(repo_dir)
    consumed_apis = scan_inter_service_calls(repo_dir)

    service_name = repo_path.split("/")[-1]

    return ServiceInventoryEntry(
        name=service_name,
        repo_path=repo_path,
        tech_stack=tech_stack,
        exposed_apis=source_scan.get("endpoints", []),
        consumed_apis=consumed_apis,
        data_stores=data_stores,
        ci_config=ci_config,
    )


def correlate_communication(services: list[ServiceInventoryEntry]) -> list[CommunicationLink]:
    links: list[CommunicationLink] = []
    service_ports: dict[str, str] = {}

    for svc in services:
        app_yml = Path(svc.repo_path) if Path(svc.repo_path).exists() else None
        for consumed in svc.consumed_apis:
            target = consumed.target_service
            if target == "unknown" or target == "localhost service":
                for other_svc in services:
                    if other_svc.name != svc.name:
                        for api in other_svc.exposed_apis:
                            if api.path in consumed.url_pattern:
                                target = other_svc.name
                                break

            if target != "unknown":
                links.append(CommunicationLink(
                    source_service=svc.name,
                    target_service=target,
                    protocol=consumed.protocol,
                    direction="sync",
                ))

    return links


def scan_repos(
    repo_paths: list[str], git_ops: GitOps
) -> BaselineDocument:
    services: list[ServiceInventoryEntry] = []
    all_refs: list[ExternalRef] = []

    for repo_path in repo_paths:
        repo_dir = git_ops.clone_repo(repo_path)
        svc = scan_single_repo(repo_dir, repo_path)
        services.append(svc)
        all_refs.extend(scan_external_references(repo_dir))

    links = correlate_communication(services)

    return BaselineDocument(
        repos_scanned=repo_paths,
        branches_scanned=["main"],
        services=services,
        communication_links=links,
        external_references=all_refs,
    )
