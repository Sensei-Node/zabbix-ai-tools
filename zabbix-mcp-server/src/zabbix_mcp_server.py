#!/usr/bin/env python3
"""
Zabbix MCP Server - Complete integration with Zabbix API using python-zabbix-utils

This server provides comprehensive access to Zabbix API functionality through
the Model Context Protocol (MCP), enabling AI assistants and other tools to
interact with Zabbix monitoring systems.

Author: Zabbix MCP Server Contributors
License: MIT
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP
from zabbix_utils import ZabbixAPI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.getenv("DEBUG") else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("Zabbix MCP Server")

# Global Zabbix API client
zabbix_api: Optional[ZabbixAPI] = None


def get_zabbix_client() -> ZabbixAPI:
    """Get or create Zabbix API client with proper authentication.

    Returns:
        ZabbixAPI: Authenticated Zabbix API client

    Raises:
        ValueError: If required environment variables are missing
        Exception: If authentication fails
    """
    global zabbix_api

    if zabbix_api is None:
        url = os.getenv("ZABBIX_URL")
        if not url:
            raise ValueError("ZABBIX_URL environment variable is required")

        logger.info(f"Initializing Zabbix API client for {url}")

        # Initialize client
        zabbix_api = ZabbixAPI(url=url)

        # Authenticate using token or username/password
        token = os.getenv("ZABBIX_TOKEN")
        if token:
            logger.info("Authenticating with API token")
            zabbix_api.login(token=token)
        else:
            user = os.getenv("ZABBIX_USER")
            password = os.getenv("ZABBIX_PASSWORD")
            if not user or not password:
                raise ValueError(
                    "Either ZABBIX_TOKEN or ZABBIX_USER/ZABBIX_PASSWORD must be set"
                )
            logger.info(f"Authenticating with username: {user}")
            zabbix_api.login(user=user, password=password)

        logger.info("Successfully authenticated with Zabbix API")

    return zabbix_api


def is_read_only() -> bool:
    """Check if server is in read-only mode.

    Returns:
        bool: True if read-only mode is enabled
    """
    return os.getenv("READ_ONLY", "true").lower() in ("true", "1", "yes")


def format_response(data: Any) -> str:
    """Format response data as JSON string.

    Args:
        data: Data to format

    Returns:
        str: JSON formatted string
    """
    return json.dumps(data, indent=2, default=str)


def validate_read_only() -> None:
    """Validate that write operations are allowed.

    Raises:
        ValueError: If server is in read-only mode
    """
    if is_read_only():
        raise ValueError(
            "Server is in read-only mode - write operations are not allowed"
        )


# HOST MANAGEMENT
@mcp.tool()
def host_get(
    hostids: Optional[List[str]] = None,
    groupids: Optional[List[str]] = None,
    templateids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> str:
    """Get hosts from Zabbix with optional filtering.

    This tool retrieves host information from Zabbix. Hosts are the central entity in Zabbix that runs agents and gets monitored. Use filtering parameters to narrow down results and always specify a limit for large installations to prevent overwhelming responses.

    Args:
        hostids: Optional list of host IDs to retrieve specific hosts. Example: ["10084", "10085"].
        groupids: Optional list of host group IDs to filter hosts belonging to these groups.
        templateids: Optional list of template IDs to filter hosts linked to these templates.
        output: Specifies the output format. Use "extend" for all fields (default), "shorten" for basic fields, or a list of specific fields like ["hostid", "host", "name"].
        search: Optional dictionary for wildcard searching in host fields, e.g., {"host": "Linux*"} to find hosts with technical names starting with "Linux".
        filter: Optional dictionary for exact matching on host properties, e.g., {"status": 0} for enabled hosts.
        limit: Optional integer to limit the number of returned hosts. Strongly recommended to use this (e.g., 100) to avoid large responses that may cause failures or timeouts.

    Returns:
        str: JSON formatted list of hosts with their details.

    Notes:
        - Without filters or limit, this may return a very large number of hosts in big environments, potentially causing the tool to fail. Always use limit and filters for efficiency.
        - For more details, refer to Zabbix API documentation for host.get method.
        - Example usage: host_get(filter={"host": ["Zabbix server", "Linux server"]}, output="extend", limit=10) to get up to 10 hosts matching specific names with all details.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if hostids:
        params["hostids"] = hostids
    if groupids:
        params["groupids"] = groupids
    if templateids:
        params["templateids"] = templateids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter
    if limit:
        params["limit"] = limit

    result = client.host.get(**params)
    return format_response(result)


@mcp.tool()
def host_create(
    host: str,
    groups: List[Dict[str, str]],
    interfaces: List[Dict[str, Any]],
    templates: Optional[List[Dict[str, str]]] = None,
    inventory_mode: int = -1,
    status: int = 0,
) -> str:
    """Create a new host in Zabbix.

    Args:
        host: Host name
        groups: List of host groups (format: [{"groupid": "1"}])
        interfaces: List of host interfaces
        templates: List of templates to link (format: [{"templateid": "1"}])
        inventory_mode: Inventory mode (-1=disabled, 0=manual, 1=automatic)
        status: Host status (0=enabled, 1=disabled)

    Returns:
        str: JSON formatted creation result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {
        "host": host,
        "groups": groups,
        "interfaces": interfaces,
        "inventory_mode": inventory_mode,
        "status": status,
    }

    if templates:
        params["templates"] = templates

    result = client.host.create(**params)
    return format_response(result)


@mcp.tool()
def host_update(
    hostid: str,
    host: Optional[str] = None,
    name: Optional[str] = None,
    status: Optional[int] = None,
) -> str:
    """Update an existing host in Zabbix.

    Args:
        hostid: Host ID to update
        host: New host name
        name: New visible name
        status: New status (0=enabled, 1=disabled)

    Returns:
        str: JSON formatted update result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"hostid": hostid}

    if host:
        params["host"] = host
    if name:
        params["name"] = name
    if status is not None:
        params["status"] = status

    result = client.host.update(**params)
    return format_response(result)


@mcp.tool()
def host_delete(hostids: List[str]) -> str:
    """Delete hosts from Zabbix.

    Args:
        hostids: List of host IDs to delete

    Returns:
        str: JSON formatted deletion result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.host.delete(*hostids)
    return format_response(result)


# HOST GROUP MANAGEMENT
@mcp.tool()
def hostgroup_get(
    groupids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> str:
    """Get host groups from Zabbix with optional filtering.

    This tool retrieves host group information from Zabbix. Host groups are used to group monitored hosts for easier management, permissions, and configuration. Use filtering parameters to narrow down results and prevent overwhelming responses in large installations.

    Args:
        groupids: Optional list of host group IDs to retrieve specific groups. Example: ["2", "4"].
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["groupid", "name", "internal"].
        search: Optional dictionary for wildcard searching in host group fields, e.g., {"name": "Linux*"} to find groups with names starting with "Linux".
        filter: Optional dictionary for exact matching on host group properties, e.g., {"name": ["Zabbix servers", "Linux servers"]} for specific group names.

    Returns:
        str: JSON formatted list of host groups with their details.

    Notes:
        - Without filters, this may return a very large number of host groups in big environments, potentially causing the tool to fail. Always use filters for efficiency.
        - Example usage: hostgroup_get(filter={"name": ["Zabbix servers", "Linux servers"]}, output="extend") to get details of specific host groups.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if groupids:
        params["groupids"] = groupids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter

    result = client.hostgroup.get(**params)
    return format_response(result)


@mcp.tool()
def hostgroup_create(name: str) -> str:
    """Create a new host group in Zabbix.

    Args:
        name: Host group name

    Returns:
        str: JSON formatted creation result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.hostgroup.create(name=name)
    return format_response(result)


@mcp.tool()
def hostgroup_update(groupid: str, name: str) -> str:
    """Update an existing host group in Zabbix.

    Args:
        groupid: Group ID to update
        name: New group name

    Returns:
        str: JSON formatted update result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.hostgroup.update(groupid=groupid, name=name)
    return format_response(result)


@mcp.tool()
def hostgroup_delete(groupids: List[str]) -> str:
    """Delete host groups from Zabbix.

    Args:
        groupids: List of group IDs to delete

    Returns:
        str: JSON formatted deletion result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.hostgroup.delete(*groupids)
    return format_response(result)


# ITEM MANAGEMENT
@mcp.tool()
def item_get(
    itemids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    groupids: Optional[List[str]] = None,
    templateids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> str:
    """Get items from Zabbix with optional filtering.

    This tool retrieves monitoring item information from Zabbix. Items define what data is collected from hosts (e.g., CPU load, disk space). Use filtering parameters to narrow down results and always specify a limit for large installations to prevent overwhelming responses.

    Args:
        itemids: Optional list of item IDs to retrieve specific items. Example: ["23296", "23297"].
        hostids: Optional list of host IDs to filter items associated with specific hosts.
        groupids: Optional list of host group IDs to filter items from hosts in these groups.
        templateids: Optional list of template IDs to filter items from specific templates.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["itemid", "name", "key_", "value_type"].
        search: Optional dictionary for wildcard searching in item fields, e.g., {"key_": "system.cpu*"} to find items related to CPU.
        filter: Optional dictionary for exact matching on item properties, e.g., {"type": 0, "status": 0} for enabled Zabbix agent items.
        limit: Optional integer to limit the number of returned items. Strongly recommended to use this (e.g., 100) to avoid large responses that may cause failures or timeouts.

    Returns:
        str: JSON formatted list of items with their details.

    Notes:
        - Without filters or limit, this may return a very large number of items in big environments, potentially causing the tool to fail. Always use limit and filters for efficiency.
        - For more details, refer to Zabbix API documentation for item.get method.
        - Example usage: item_get(hostids=["10084"], filter={"value_type": 3}, limit=50) to get up to 50 numeric unsigned items from host 10084.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if itemids:
        params["itemids"] = itemids
    if hostids:
        params["hostids"] = hostids
    if groupids:
        params["groupids"] = groupids
    if templateids:
        params["templateids"] = templateids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter
    if limit:
        params["limit"] = limit

    result = client.item.get(**params)
    return format_response(result)


@mcp.tool()
def item_create(
    name: str,
    key_: str,
    hostid: str,
    type: int,
    value_type: int,
    delay: str = "1m",
    units: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Create a new item in Zabbix.

    Args:
        name: Item name
        key_: Item key
        hostid: Host ID
        type: Item type (0=Zabbix agent, 2=Zabbix trapper, etc.)
        value_type: Value type (0=float, 1=character, 3=unsigned int, 4=text)
        delay: Update interval
        units: Value units
        description: Item description

    Returns:
        str: JSON formatted creation result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {
        "name": name,
        "key_": key_,
        "hostid": hostid,
        "type": type,
        "value_type": value_type,
        "delay": delay,
    }

    if units:
        params["units"] = units
    if description:
        params["description"] = description

    result = client.item.create(**params)
    return format_response(result)


@mcp.tool()
def item_update(
    itemid: str,
    name: Optional[str] = None,
    key_: Optional[str] = None,
    delay: Optional[str] = None,
    status: Optional[int] = None,
) -> str:
    """Update an existing item in Zabbix.

    Args:
        itemid: Item ID to update
        name: New item name
        key_: New item key
        delay: New update interval
        status: New status (0=enabled, 1=disabled)

    Returns:
        str: JSON formatted update result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"itemid": itemid}

    if name:
        params["name"] = name
    if key_:
        params["key_"] = key_
    if delay:
        params["delay"] = delay
    if status is not None:
        params["status"] = status

    result = client.item.update(**params)
    return format_response(result)


@mcp.tool()
def item_delete(itemids: List[str]) -> str:
    """Delete items from Zabbix.

    Args:
        itemids: List of item IDs to delete

    Returns:
        str: JSON formatted deletion result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.item.delete(*itemids)
    return format_response(result)


# TRIGGER MANAGEMENT
@mcp.tool()
def trigger_get(
    triggerids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    groupids: Optional[List[str]] = None,
    templateids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> str:
    """Get triggers from Zabbix with optional filtering.

    This tool retrieves trigger information from Zabbix. Triggers define conditions under which problems are detected in monitoring data. Use filtering parameters to narrow down results and always specify a limit for large installations to prevent overwhelming responses.

    Args:
        triggerids: Optional list of trigger IDs to retrieve specific triggers. Example: ["12345", "67890"].
        hostids: Optional list of host IDs to filter triggers associated with specific hosts.
        groupids: Optional list of host group IDs to filter triggers from hosts in these groups.
        templateids: Optional list of template IDs to filter triggers from specific templates.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["triggerid", "description", "priority"].
        search: Optional dictionary for wildcard searching in trigger fields, e.g., {"description": "CPU*"} to find triggers with descriptions starting with "CPU".
        filter: Optional dictionary for exact matching on trigger properties, e.g., {"priority": 4} for high severity triggers.
        limit: Optional integer to limit the number of returned triggers. Strongly recommended to use this (e.g., 100) to avoid large responses that may cause failures or timeouts.

    Returns:
        str: JSON formatted list of triggers with their details.

    Notes:
        - Without filters or limit, this may return a very large number of triggers in big environments, potentially causing the tool to fail. Always use limit and filters for efficiency.
        - For more details, refer to Zabbix API documentation for trigger.get method.
        - Example usage: trigger_get(hostids=["10001"], filter={"status": 0}, limit=50) to get up to 50 enabled triggers from host 10001.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if triggerids:
        params["triggerids"] = triggerids
    if hostids:
        params["hostids"] = hostids
    if groupids:
        params["groupids"] = groupids
    if templateids:
        params["templateids"] = templateids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter
    if limit:
        params["limit"] = limit

    result = client.trigger.get(**params)
    return format_response(result)


@mcp.tool()
def trigger_create(
    description: str,
    expression: str,
    priority: int = 0,
    status: int = 0,
    comments: Optional[str] = None,
) -> str:
    """Create a new trigger in Zabbix.

    Args:
        description: Trigger description
        expression: Trigger expression
        priority: Severity (0=not classified, 1=P4, 2=P3, 3=P2, 4=P1, 5=P0)
        status: Status (0=enabled, 1=disabled)
        comments: Additional comments

    Returns:
        str: JSON formatted creation result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {
        "description": description,
        "expression": expression,
        "priority": priority,
        "status": status,
    }

    if comments:
        params["comments"] = comments

    result = client.trigger.create(**params)
    return format_response(result)


@mcp.tool()
def trigger_update(
    triggerid: str,
    description: Optional[str] = None,
    expression: Optional[str] = None,
    priority: Optional[int] = None,
    status: Optional[int] = None,
) -> str:
    """Update an existing trigger in Zabbix.

    Args:
        triggerid: Trigger ID to update
        description: New trigger description
        expression: New trigger expression
        priority: New severity level
        status: New status (0=enabled, 1=disabled)

    Returns:
        str: JSON formatted update result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"triggerid": triggerid}

    if description:
        params["description"] = description
    if expression:
        params["expression"] = expression
    if priority is not None:
        params["priority"] = priority
    if status is not None:
        params["status"] = status

    result = client.trigger.update(**params)
    return format_response(result)


@mcp.tool()
def trigger_delete(triggerids: List[str]) -> str:
    """Delete triggers from Zabbix.

    Args:
        triggerids: List of trigger IDs to delete

    Returns:
        str: JSON formatted deletion result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.trigger.delete(*triggerids)
    return format_response(result)


# TEMPLATE MANAGEMENT
@mcp.tool()
def template_get(
    templateids: Optional[List[str]] = None,
    groupids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> str:
    """Get templates from Zabbix with optional filtering.

    This tool retrieves template information from Zabbix. Templates are sets of entities (items, triggers, etc.) that can be linked to multiple hosts for consistent monitoring configuration. Use filtering parameters to narrow down results and prevent overwhelming responses in large installations.

    Args:
        templateids: Optional list of template IDs to retrieve specific templates. Example: ["10001", "10081"].
        groupids: Optional list of host group IDs to filter templates associated with hosts in these groups.
        hostids: Optional list of host IDs to filter templates linked to these hosts.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["templateid", "host", "name"].
        search: Optional dictionary for wildcard searching in template fields, e.g., {"host": "Template OS*"} to find templates starting with "Template OS".
        filter: Optional dictionary for exact matching on template properties, e.g., {"host": ["Template OS Linux", "Template OS Windows"]} for specific template technical names.

    Returns:
        str: JSON formatted list of templates with their details.

    Notes:
        - Without filters, this may return a very large number of templates in big environments, potentially causing the tool to fail. Always use filters for efficiency.
        - For more details, refer to Zabbix API documentation for template.get method.
        - Example usage: template_get(filter={"host": ["Template OS Linux", "Template OS Windows"]}, output="extend") to get all details of specific templates by their technical names.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if templateids:
        params["templateids"] = templateids
    if groupids:
        params["groupids"] = groupids
    if hostids:
        params["hostids"] = hostids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter

    result = client.template.get(**params)
    return format_response(result)


@mcp.tool()
def template_create(
    host: str,
    groups: List[Dict[str, str]],
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Create a new template in Zabbix.

    Args:
        host: Template technical name
        groups: List of host groups (format: [{"groupid": "1"}])
        name: Template visible name
        description: Template description

    Returns:
        str: JSON formatted creation result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"host": host, "groups": groups}

    if name:
        params["name"] = name
    if description:
        params["description"] = description

    result = client.template.create(**params)
    return format_response(result)


@mcp.tool()
def template_update(
    templateid: str,
    host: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Update an existing template in Zabbix.

    Args:
        templateid: Template ID to update
        host: New template technical name
        name: New template visible name
        description: New template description

    Returns:
        str: JSON formatted update result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"templateid": templateid}

    if host:
        params["host"] = host
    if name:
        params["name"] = name
    if description:
        params["description"] = description

    result = client.template.update(**params)
    return format_response(result)


@mcp.tool()
def template_delete(templateids: List[str]) -> str:
    """Delete templates from Zabbix.

    Args:
        templateids: List of template IDs to delete

    Returns:
        str: JSON formatted deletion result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.template.delete(*templateids)
    return format_response(result)


# PROBLEM MANAGEMENT
@mcp.tool()
def problem_get(
    eventids: Optional[List[str]] = None,
    groupids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    objectids: Optional[List[str]] = None,
    output: str = "extend",
    time_from: Optional[int] = None,
    time_till: Optional[int] = None,
    recent: bool = False,
    severities: Optional[List[int]] = None,
    limit: Optional[int] = None,
) -> str:
    """Get problems from Zabbix with optional filtering.

    This tool retrieves information about current problems in Zabbix. Problems represent unresolved events generated by triggers, low-level discovery rules, or internal services. Use time-based and severity filters to narrow results, and always specify a limit to prevent overwhelming responses in active monitoring environments.

    Args:
        eventids: Optional list of event IDs to retrieve problems for specific events. Example: ["12345", "67890"].
        groupids: Optional list of host group IDs to filter problems from hosts in these groups.
        hostids: Optional list of host IDs to filter problems associated with specific hosts.
        objectids: Optional list of object IDs (e.g., trigger IDs) to filter problems generated by these objects.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["eventid", "severity", "name"].
        time_from: Optional Unix timestamp to filter problems starting from this time.
        time_till: Optional Unix timestamp to filter problems up to this time.
        recent: If true, retrieve only recent (unacknowledged) problems. Default: false.
        severities: Optional list of severity levels to filter by (0=not classified, 1=P4, 2=P3, 3=P2, 4=P1, 5=P0).
        limit: Optional integer to limit the number of returned problems. Strongly recommended to use this (e.g., 100) to avoid large responses that may cause failures or timeouts.

    Returns:
        str: JSON formatted list of problems with their details.

    Notes:
        - Without time filters or limit, this may return a very large number of problems, especially in environments with many active issues, potentially causing the tool to fail. Always combine with time_from/time_till and limit for efficiency.
        - For more details, refer to Zabbix API documentation for problem.get method.
        - Example usage: problem_get(hostids=["10084"], severities=[4,5], time_from=1690000000, limit=50) to get up to 50 high/disaster severity problems from host 10084 since a specific timestamp.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if eventids:
        params["eventids"] = eventids
    if groupids:
        params["groupids"] = groupids
    if hostids:
        params["hostids"] = hostids
    if objectids:
        params["objectids"] = objectids
    if time_from:
        params["time_from"] = time_from
    if time_till:
        params["time_till"] = time_till
    if recent:
        params["recent"] = recent
    if severities:
        params["severities"] = severities
    if limit:
        params["limit"] = limit

    result = client.problem.get(**params)
    return format_response(result)


# EVENT MANAGEMENT
@mcp.tool()
def event_get(
    eventids: Optional[List[str]] = None,
    groupids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    objectids: Optional[List[str]] = None,
    output: str = "extend",
    time_from: Optional[int] = None,
    time_till: Optional[int] = None,
    limit: Optional[int] = None,
) -> str:
    """Get events from Zabbix with optional filtering.

    This tool retrieves event information from Zabbix. Events are generated by triggers, internal processes, or other sources, representing changes in monitored data. Use time-based filters and limit to avoid large responses, which commonly cause failures. Ensure parameters like IDs are strings and timestamps are integers to prevent type errors.

    Args:
        eventids: Optional list of event IDs (as strings) to retrieve specific events. If unknown, use problem_get to find relevant event IDs or ask the user.
        groupids: Optional list of host group IDs (as strings) to filter events from hosts in these groups. If unclear, use hostgroup_get to retrieve group IDs first.
        hostids: Optional list of host IDs (as strings) to filter events associated with specific hosts. If unknown, use host_get to find host IDs or ask the user.
        objectids: Optional list of object IDs (as strings, e.g., trigger IDs) to filter events generated by these objects. If unclear, use trigger_get to retrieve object IDs first.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["eventid", "clock", "value"] as strings.
        time_from: Optional start time as Unix timestamp (integer). If unknown, calculate from a known date or ask the user for a time range.
        time_till: Optional end time as Unix timestamp (integer). If unknown, calculate from a known date or ask the user for a time range.
        limit: Optional integer to limit the number of returned events. Strongly recommended to use this (e.g., 100) to avoid large responses that may cause failures or timeouts; common issue without it.

    Returns:
        str: JSON formatted list of events with their details.

    Notes:
        - This tool often fails due to very large responses without limit or filters (e.g., thousands of events). Always specify limit and time_from/time_till for efficiency.
        - Type errors are common; ensure IDs are lists of strings and timestamps are integers. If unsure about a parameter, use related tools like host_get or trigger_get to fetch values first, or ask the user.
        - Example usage: event_get(hostids=["10084"], time_from=1690000000, time_till=1691000000, limit=50) to get up to 50 events from host 10084 within a specific time range.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if eventids:
        params["eventids"] = eventids
    if groupids:
        params["groupids"] = groupids
    if hostids:
        params["hostids"] = hostids
    if objectids:
        params["objectids"] = objectids
    if time_from:
        params["time_from"] = time_from
    if time_till:
        params["time_till"] = time_till
    if limit:
        params["limit"] = limit

    result = client.event.get(**params)
    return format_response(result)


@mcp.tool()
def event_acknowledge(
    eventids: List[str], action: int = 1, message: Optional[str] = None
) -> str:
    """Acknowledge events in Zabbix.

    Args:
        eventids: List of event IDs to acknowledge
        action: Acknowledge action (1=acknowledge, 2=close, etc.)
        message: Acknowledge message

    Returns:
        str: JSON formatted acknowledgment result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"eventids": eventids, "action": action}

    if message:
        params["message"] = message

    result = client.event.acknowledge(**params)
    return format_response(result)


# HISTORY MANAGEMENT
@mcp.tool()
def history_get(
    hostids: List[str],
    itemids: List[str],
    history: List[int] = [0, 1, 3, 4],
    time_from: Optional[int] = None,
    time_till: Optional[int] = None,
    limit: Optional[int] = 10,
    sortfield: str = "clock",
    sortorder: str = "DESC",
    output: str = "extend",
) -> str:
    """Get history data from Zabbix.

    This tool retrieves historical monitoring data for specified items.
    History data includes timestamped values collected over time.
    Use time ranges and limits to manage response size, as large queries can fail due to excessive data.

    Args:
        hostids: Required list hosts (as strings) to get history for. Example: for multiple hosts ["678296", "21353"] or for single hosts ["412313"]
        itemids: Required list of item IDs (as strings) to get history for. Example: ["23296", "23297"]. If unknown, use item_get to find item IDs first or ask the user.
        history: Type of history data: 0=float (default), 1=string, 2=log, 3=integer, 4=text. Choose based on the item's value_type.
        time_from: Optional start time as Unix timestamp (integer). If unknown, calculate from a known date or ask the user.
        time_till: Optional end time as Unix timestamp (integer). If unknown, calculate from a known date or ask the user.
        limit: Optional integer to limit the number of returned values. Strongly recommended (e.g., 10) to avoid failures from massive datasets.
        sortfield: Field to sort by, e.g., "clock" (default) for timestamp.
        sortorder: Sort order: "DESC" (default) for newest first, or "ASC".
        output (extend): Return all objects. Always required.

    Returns:
        str: JSON formatted list of history data points, each with timestamp, value, etc.

    Notes:
        - Use hostids when possible to only fetch relevant data. You can ignore this argument only if the current problem or special context justify it.
        - Always request all data types except logs (2). You can pass a different list only if requested by the human operator.
        - Queries without time_from/time_till or limit can return enormous amounts of data (e.g., years of metrics), causing failures. Always specify a narrow time range and limit.
        - Type errors are common; ensure itemids are strings in a list and timestamps are integers. If unsure, use item_get to verify item details.
        - Example usage: history_get(hostids=["312451"], itemids=["23296"], history=[0, 1, 3, 4], time_from=1690000000, time_till=1691000000, limit=10, sortorder="ASC", output="extend")
        to get up to 10  values from all types that we usually use or that was requested for an item in a time range, sorted oldest first.
    """

    history_results = []
    client = get_zabbix_client()
    for data_type in history:
        params = {
            "itemids": itemids,
            "history": data_type,
            "sortfield": sortfield,
            "sortorder": sortorder,
        }

        if time_from:
            params["time_from"] = time_from
        if time_till:
            params["time_till"] = time_till
        if limit:
            params["limit"] = limit

        history_results.append(client.history.get(**params))

    return format_response(history_results)


# TREND MANAGEMENT
@mcp.tool()
def trend_get(
    itemids: List[str],
    time_from: Optional[int] = None,
    time_till: Optional[int] = None,
    limit: Optional[int] = None,
) -> str:
    """Get trend data from Zabbix.

    This tool retrieves aggregated trend data (min, max, avg, count) for specified items over time periods (typically hourly). Trends are pre-computed summaries for long-term analysis. Use time ranges and limits to control response size.

    Args:
        itemids: Required list of item IDs (as strings) to get trends for. Example: ["23296", "23297"]. If unknown, use item_get to find item IDs first or ask the user.
        time_from: Optional start time as Unix timestamp (integer). If unknown, calculate from a known date or ask the user.
        time_till: Optional end time as Unix timestamp (integer). If unknown, calculate from a known date or ask the user.
        limit: Optional integer to limit the number of returned trend records. Strongly recommended (e.g., 1000) to avoid failures from large time ranges.

    Returns:
        str: JSON formatted list of trend data points, each with period, min, max, avg, etc.

    Notes:
        - Without time_from/time_till or limit, this can return massive datasets (e.g., years of hourly trends), causing failures. Always specify a time range and limit.
        - Ensure itemids are strings in a list and timestamps are integers to avoid type errors. If unsure, use item_get to verify.
        - Example usage: trend_get(itemids=["23296"], time_from=1690000000, time_till=1691000000, limit=1000) to get up to 1000 trend records for an item in a specific time range.
    """
    client = get_zabbix_client()
    params = {"itemids": itemids}

    if time_from:
        params["time_from"] = time_from
    if time_till:
        params["time_till"] = time_till
    if limit:
        params["limit"] = limit

    result = client.trend.get(**params)
    return format_response(result)


# USER MANAGEMENT
@mcp.tool()
def user_get(
    userids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> str:
    """Get users from Zabbix with optional filtering.

    Args:
        userids: List of user IDs to retrieve
        output: Output format
        search: Search criteria
        filter: Filter criteria

    Returns:
        str: JSON formatted list of users
    """
    client = get_zabbix_client()
    params = {"output": output}

    if userids:
        params["userids"] = userids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter

    result = client.user.get(**params)
    return format_response(result)


@mcp.tool()
def user_create(
    username: str,
    passwd: str,
    usrgrps: List[Dict[str, str]],
    name: Optional[str] = None,
    surname: Optional[str] = None,
    email: Optional[str] = None,
) -> str:
    """Create a new user in Zabbix.

    Args:
        username: Username
        passwd: Password
        usrgrps: List of user groups (format: [{"usrgrpid": "1"}])
        name: First name
        surname: Last name
        email: Email address

    Returns:
        str: JSON formatted creation result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"username": username, "passwd": passwd, "usrgrps": usrgrps}

    if name:
        params["name"] = name
    if surname:
        params["surname"] = surname
    if email:
        params["email"] = email

    result = client.user.create(**params)
    return format_response(result)


@mcp.tool()
def user_update(
    userid: str,
    username: Optional[str] = None,
    name: Optional[str] = None,
    surname: Optional[str] = None,
    email: Optional[str] = None,
) -> str:
    """Update an existing user in Zabbix.

    Args:
        userid: User ID to update
        username: New username
        name: New first name
        surname: New last name
        email: New email address

    Returns:
        str: JSON formatted update result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"userid": userid}

    if username:
        params["username"] = username
    if name:
        params["name"] = name
    if surname:
        params["surname"] = surname
    if email:
        params["email"] = email

    result = client.user.update(**params)
    return format_response(result)


@mcp.tool()
def user_delete(userids: List[str]) -> str:
    """Delete users from Zabbix.

    Args:
        userids: List of user IDs to delete

    Returns:
        str: JSON formatted deletion result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.user.delete(*userids)
    return format_response(result)


# MAINTENANCE MANAGEMENT
@mcp.tool()
def maintenance_get(
    maintenanceids: Optional[List[str]] = None,
    groupids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    output: str = "extend",
) -> str:
    """Get maintenance periods from Zabbix with optional filtering.

    This tool retrieves information about scheduled maintenance periods in Zabbix, during which monitoring and alerts are suppressed. Use filters to narrow results in environments with many maintenance windows.

    Args:
        maintenanceids: Optional list of maintenance IDs (as strings) to retrieve specific maintenance periods. Example: ["1", "2"]. If unknown, ask the user or use other tools to discover.
        groupids: Optional list of host group IDs (as strings) to filter maintenance affecting these groups. If unclear, use hostgroup_get to retrieve group IDs first.
        hostids: Optional list of host IDs (as strings) to filter maintenance affecting these hosts. If unknown, use host_get to find host IDs or ask the user.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["maintenanceid", "name", "active_since"].

    Returns:
        str: JSON formatted list of maintenance periods with their details.

    Notes:
        - Without filters, this may return a large number of maintenance periods in busy environments, potentially causing performance issues. Always use filters for efficiency.
        - Ensure IDs are lists of strings to avoid type errors. If unsure about parameters, use related tools like host_get or hostgroup_get to fetch values first, or ask the user.
        - Example usage: maintenance_get(hostids=["10084"], output="extend") to get all maintenance periods affecting a specific host with full details.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if maintenanceids:
        params["maintenanceids"] = maintenanceids
    if groupids:
        params["groupids"] = groupids
    if hostids:
        params["hostids"] = hostids

    result = client.maintenance.get(**params)
    return format_response(result)


@mcp.tool()
def maintenance_create(
    name: str,
    active_since: int,
    active_till: int,
    groupids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    timeperiods: Optional[List[Dict[str, Any]]] = None,
    description: Optional[str] = None,
) -> str:
    """Create a new maintenance period in Zabbix.

    Args:
        name: Maintenance name
        active_since: Start time (Unix timestamp)
        active_till: End time (Unix timestamp)
        groupids: List of host group IDs
        hostids: List of host IDs
        timeperiods: List of time periods
        description: Maintenance description

    Returns:
        str: JSON formatted creation result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"name": name, "active_since": active_since, "active_till": active_till}

    if groupids:
        params["groupids"] = groupids
    if hostids:
        params["hostids"] = hostids
    if timeperiods:
        params["timeperiods"] = timeperiods
    if description:
        params["description"] = description

    result = client.maintenance.create(**params)
    return format_response(result)


@mcp.tool()
def maintenance_update(
    maintenanceid: str,
    name: Optional[str] = None,
    active_since: Optional[int] = None,
    active_till: Optional[int] = None,
    description: Optional[str] = None,
) -> str:
    """Update an existing maintenance period in Zabbix.

    Args:
        maintenanceid: Maintenance ID to update
        name: New maintenance name
        active_since: New start time (Unix timestamp)
        active_till: New end time (Unix timestamp)
        description: New maintenance description

    Returns:
        str: JSON formatted update result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"maintenanceid": maintenanceid}

    if name:
        params["name"] = name
    if active_since:
        params["active_since"] = active_since
    if active_till:
        params["active_till"] = active_till
    if description:
        params["description"] = description

    result = client.maintenance.update(**params)
    return format_response(result)


@mcp.tool()
def maintenance_delete(maintenanceids: List[str]) -> str:
    """Delete maintenance periods from Zabbix.

    Args:
        maintenanceids: List of maintenance IDs to delete

    Returns:
        str: JSON formatted deletion result
    """
    validate_read_only()

    client = get_zabbix_client()
    result = client.maintenance.delete(*maintenanceids)
    return format_response(result)


# GRAPH MANAGEMENT
@mcp.tool()
def graph_get(
    graphids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    templateids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> str:
    """Get graphs from Zabbix with optional filtering.

    This tool retrieves graph configurations from Zabbix, which visualize multiple items' data over time. Use filters to narrow results in environments with many graphs.

    Args:
        graphids: Optional list of graph IDs (as strings) to retrieve specific graphs. Example: ["612", "613"]. If unknown, ask the user or use other tools to discover.
        hostids: Optional list of host IDs (as strings) to filter graphs associated with these hosts. If unclear, use host_get to retrieve host IDs first.
        templateids: Optional list of template IDs (as strings) to filter graphs from these templates. If unknown, use template_get to find template IDs or ask the user.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["graphid", "name", "width"].
        search: Optional dictionary for wildcard searching in graph fields, e.g., {"name": "CPU*"} to find graphs with names starting with "CPU".
        filter: Optional dictionary for exact matching on graph properties, e.g., {"graphtype": 0} for normal graphs.

    Returns:
        str: JSON formatted list of graphs with their details.

    Notes:
        - Without filters, this may return a large number of graphs in complex setups, potentially causing performance issues. Always use filters for efficiency.
        - Ensure IDs are lists of strings to avoid type errors. If unsure about parameters, use related tools like host_get or template_get to fetch values first, or ask the user.
        - Example usage: graph_get(hostids=["10084"], filter={"graphtype": 0}, output="extend") to get all normal graphs for a specific host with full details.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if graphids:
        params["graphids"] = graphids
    if hostids:
        params["hostids"] = hostids
    if templateids:
        params["templateids"] = templateids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter

    result = client.graph.get(**params)
    return format_response(result)


# DISCOVERY RULE MANAGEMENT
@mcp.tool()
def discoveryrule_get(
    itemids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    templateids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> str:
    """Get discovery rules from Zabbix with optional filtering.

    Args:
        itemids: List of discovery rule IDs to retrieve
        hostids: List of host IDs to filter by
        templateids: List of template IDs to filter by
        output: Output format
        search: Search criteria
        filter: Filter criteria

    Returns:
        str: JSON formatted list of discovery rules
    """
    client = get_zabbix_client()
    params = {"output": output}

    if itemids:
        params["itemids"] = itemids
    if hostids:
        params["hostids"] = hostids
    if templateids:
        params["templateids"] = templateids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter

    result = client.discoveryrule.get(**params)
    return format_response(result)


# ITEM PROTOTYPE MANAGEMENT
@mcp.tool()
def itemprototype_get(
    itemids: Optional[List[str]] = None,
    discoveryids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> str:
    """Get item prototypes from Zabbix with optional filtering.

    This tool retrieves item prototype information from Zabbix. Item prototypes are templates for items that are automatically created during low-level discovery (LLD) processes. Use filters to narrow results in environments with many prototypes.

    Args:
        itemids: Optional list of item prototype IDs (as strings) to retrieve specific prototypes. Example: ["12345", "67890"]. If unknown, ask the user or use other tools to discover.
        discoveryids: Optional list of discovery rule IDs (as strings) to filter prototypes belonging to these LLD rules. If unclear, use discoveryrule_get to retrieve discovery rule IDs first.
        hostids: Optional list of host IDs (as strings) to filter prototypes associated with these hosts or templates. If unknown, use host_get or template_get to find IDs or ask the user.
        output: Specifies the output format. Use "extend" for all fields (default), or a list of specific fields like ["itemid", "name", "key_", "value_type"].
        search: Optional dictionary for wildcard searching in prototype fields, e.g., {"key_": "vfs.fs*"} to find file system related prototypes.
        filter: Optional dictionary for exact matching on prototype properties, e.g., {"type": 0, "status": 0} for enabled Zabbix agent prototypes.

    Returns:
        str: JSON formatted list of item prototypes with their details.

    Notes:
        - Without filters, this may return a large number of prototypes in discovery-heavy setups, potentially causing performance issues. Always use filters for efficiency.
        - Ensure IDs are lists of strings to avoid type errors. If unsure about parameters, use related tools like discoveryrule_get or host_get to fetch values first, or ask the user.
        - Example usage: itemprototype_get(discoveryids=["123"], filter={"value_type": 3}, output="extend") to get all numeric unsigned item prototypes from a specific discovery rule with full details.
    """
    client = get_zabbix_client()
    params = {"output": output}

    if itemids:
        params["itemids"] = itemids
    if discoveryids:
        params["discoveryids"] = discoveryids
    if hostids:
        params["hostids"] = hostids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter

    result = client.itemprototype.get(**params)
    return format_response(result)


# CONFIGURATION EXPORT/IMPORT
@mcp.tool()
def configuration_export(
    format: str = "json", options: Optional[Dict[str, Any]] = None
) -> str:
    """Export configuration from Zabbix.

    Args:
        format: Export format (json, xml)
        options: Export options

    Returns:
        str: JSON formatted export result
    """
    client = get_zabbix_client()
    params = {"format": format}

    if options:
        params["options"] = options

    result = client.configuration.export(**params)
    return format_response(result)


@mcp.tool()
def configuration_import(format: str, source: str, rules: Dict[str, Any]) -> str:
    """Import configuration to Zabbix.

    Args:
        format: Import format (json, xml)
        source: Configuration data to import
        rules: Import rules

    Returns:
        str: JSON formatted import result
    """
    validate_read_only()

    client = get_zabbix_client()
    params = {"format": format, "source": source, "rules": rules}

    result = client.configuration.import_(**params)
    return format_response(result)


# MACRO MANAGEMENT
@mcp.tool()
def usermacro_get(
    globalmacroids: Optional[List[str]] = None,
    hostids: Optional[List[str]] = None,
    output: str = "extend",
    search: Optional[Dict[str, str]] = None,
    filter: Optional[Dict[str, Any]] = None,
) -> str:
    """Get global macros from Zabbix with optional filtering.

    Args:
        globalmacroids: List of global macro IDs to retrieve
        hostids: List of host IDs to filter by (for host macros)
        output: Output format (extend, shorten, or specific fields)
        search: Search criteria
        filter: Filter criteria

    Returns:
        str: JSON formatted list of global macros
    """
    client = get_zabbix_client()
    params = {"output": output}

    if globalmacroids:
        params["globalmacroids"] = globalmacroids
    if hostids:
        params["hostids"] = hostids
    if search:
        params["search"] = search
    if filter:
        params["filter"] = filter

    result = client.usermacro.get(**params)
    return format_response(result)


# SYSTEM INFO
@mcp.tool()
def apiinfo_version() -> str:
    """Get Zabbix API version information.

    Returns:
        str: JSON formatted API version info
    """
    client = get_zabbix_client()
    result = client.apiinfo.version()
    return format_response(result)


def main():
    """Main entry point for uv execution."""
    logger.info("Starting Zabbix MCP Server")

    # Log configuration
    logger.info(f"Read-only mode: {is_read_only()}")
    logger.info(f"Zabbix URL: {os.getenv('ZABBIX_URL', 'Not configured')}")

    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
