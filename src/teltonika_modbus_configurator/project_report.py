"""Human-readable project diagnostics for commissioning and review."""

from __future__ import annotations

from collections import Counter, defaultdict

from .models import FunctionCode, Project, ServerMapping
from .register_allocator import mapping_width
from .validator import validate_project


REGISTER_TYPE_LABELS = {
    "coil": "Coils",
    "discrete_input": "Discrete Inputs",
    "holding_register": "Holding Registers",
    "input_register": "Input Registers",
}


def _all_sources(project: Project):
    return [*project.devices, *project.tcp_clients]


def _deployed_blocks(mappings: list[ServerMapping]) -> list[tuple[int, int]]:
    ranges = sorted(
        (mapping.register, mapping.register + mapping_width(mapping) - 1)
        for mapping in mappings
        if mapping.enabled and mapping.deploy
    )
    if not ranges:
        return []
    blocks = [ranges[0]]
    for start, end in ranges[1:]:
        previous_start, previous_end = blocks[-1]
        if start <= previous_end + 1:
            blocks[-1] = (previous_start, max(previous_end, end))
        else:
            blocks.append((start, end))
    return blocks


def render_project_report(project: Project, *, project_name: str = "<unsaved>") -> str:
    """Return a deterministic text report without changing the project."""
    sources = _all_sources(project)
    requests = [request for source in sources for request in source.requests]
    enabled_requests = [request for request in requests if request.enabled]
    enabled_reads = [request for request in enabled_requests if request.function.is_read]
    enabled_writes = [request for request in enabled_requests if request.function.is_write]
    disabled_writes = [request for request in requests if not request.enabled and request.function.is_write]

    deployed = [mapping for mapping in project.mappings if mapping.deploy]
    aliases = [mapping for mapping in project.mappings if not mapping.deploy]
    exported = [mapping for mapping in project.mappings if mapping.export_symbol]
    enabled_deployed = [mapping for mapping in deployed if mapping.enabled]
    read_mappings = [mapping for mapping in enabled_deployed if mapping.permissions == "r"]
    write_mappings = [mapping for mapping in enabled_deployed if mapping.permissions == "w"]
    batches = [request for request in requests if request.name.startswith("Batch_FC")]

    aliases_by_request: dict[tuple[str, str], int] = Counter(
        (mapping.device, mapping.request)
        for mapping in aliases
        if mapping.enabled and mapping.export_symbol
    )
    batched_symbols = sum(aliases_by_request.values())
    batched_physical_requests = sum(1 for count in aliases_by_request.values() if count)
    requests_avoided = sum(max(0, count - 1) for count in aliases_by_request.values())

    function_counts = Counter(int(request.function) for request in enabled_requests)
    validation = validate_project(project)
    errors = [message.message for message in validation if message.level == "error"]
    warnings = [message.message for message in validation if message.level == "warning"]

    lines = [
        "TELTONIKA MODBUS CONFIGURATOR - PROJECT REPORT",
        "=" * 48,
        f"Project: {project_name}",
        "",
        "OVERVIEW",
        "--------",
        f"Serial connections:             {len(project.connections)}",
        f"RTU devices:                    {len(project.devices)}",
        f"Modbus TCP client devices:      {len(project.tcp_clients)}",
        f"Total source devices:           {len(sources)}",
        f"All client requests:            {len(requests)}",
        f"Enabled cyclic requests:        {len(enabled_requests)}",
        f"Enabled cyclic read requests:   {len(enabled_reads)}",
        f"Disabled SCADA write requests:  {len(disabled_writes)}",
        f"Logical exported symbols:       {len(exported)}",
        f"Deployed TCP Server mappings:   {len(enabled_deployed)}",
        f"  Read mappings:                {len(read_mappings)}",
        f"  Write mappings:               {len(write_mappings)}",
        f"Symbol-only aliases:            {len(aliases)}",
        "",
        "BATCHING",
        "--------",
        f"Physical batch requests:        {len(batches)}",
        f"Logical symbols inside batches: {batched_symbols}",
        f"Batch groups with aliases:      {batched_physical_requests}",
        f"Estimated requests avoided:     {requests_avoided}",
        "",
        "ENABLED REQUESTS BY FUNCTION",
        "----------------------------",
    ]
    if function_counts:
        for function in FunctionCode:
            if function_counts[int(function)]:
                lines.append(f"FC{int(function):02d}: {function_counts[int(function)]}")
    else:
        lines.append("None")

    lines.extend(["", "TCP SERVER ADDRESS BLOCKS", "-------------------------"])
    by_type: dict[str, list[ServerMapping]] = defaultdict(list)
    for mapping in enabled_deployed:
        by_type[mapping.register_type].append(mapping)
    for register_type in ("coil", "discrete_input", "holding_register", "input_register"):
        label = REGISTER_TYPE_LABELS[register_type]
        blocks = _deployed_blocks(by_type.get(register_type, []))
        if not blocks:
            lines.append(f"{label}: none")
            continue
        rendered = ", ".join(
            str(start) if start == end else f"{start}-{end}"
            for start, end in blocks
        )
        occupied = sum(end - start + 1 for start, end in blocks)
        lines.append(f"{label}: {rendered} ({occupied} addresses)")

    lines.extend(["", "DEVICE WORKLOAD", "---------------"])
    if not sources:
        lines.append("No source devices configured.")
    for source in sources:
        kind = "RTU" if source in project.devices else "TCP"
        reads = sum(request.enabled and request.function.is_read for request in source.requests)
        writes = sum(request.enabled and request.function.is_write for request in source.requests)
        mappings = sum(
            mapping.enabled and mapping.deploy and mapping.device == source.name
            for mapping in project.mappings
        )
        lines.append(
            f"{source.name} [{kind}]: {reads} cyclic reads, "
            f"{writes} cyclic writes, {mappings} deployed mappings"
        )

    lines.extend(["", "VALIDATION", "----------"])
    lines.append(f"Errors:   {len(errors)}")
    lines.append(f"Warnings: {len(warnings)}")
    for message in errors:
        lines.append(f"ERROR: {message}")
    for message in warnings:
        lines.append(f"WARNING: {message}")

    lines.extend(["", "SAFETY CHECKS", "-------------"])
    if enabled_writes:
        lines.append(
            f"WARNING: {len(enabled_writes)} write request(s) are enabled for cyclic execution."
        )
        for source in sources:
            for request in source.requests:
                if request.enabled and request.function.is_write:
                    lines.append(f"  - {source.name}/{request.name} (FC{int(request.function):02d})")
    else:
        lines.append("OK: No write requests are enabled for cyclic execution.")
    if project.tcp_server.enabled:
        lines.append(
            f"OK: TCP Server enabled on port {project.tcp_server.port}, "
            f"Device ID {project.tcp_server.device_id}."
        )
    else:
        lines.append("WARNING: TCP Server is disabled.")

    lines.extend([
        "",
        "NOTE",
        "----",
        "The workload count is the number of configured cyclic RutOS requests,",
        "not a measured cycle time. Use Live Modbus Tester for actual response timing.",
    ])
    return "\n".join(lines) + "\n"
