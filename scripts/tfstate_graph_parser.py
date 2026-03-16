#!/usr/bin/env python3
"""
Terraform State Graph Parser

Parses a Terraform state file and generates a network graph JSON file
that can be visualized using sigma.js. The graph includes:
- Nodes: Terraform resources with their attributes
- Edges: Dependencies and references between resources

Usage:
    python tfstate_graph_parser.py <path_to_tfstate> [output_dir]
"""

import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict


class TerraformStateParser:
    """Parses Terraform state files and extracts dependency graphs."""

    def __init__(self, tfstate_path: str):
        self.tfstate_path = Path(tfstate_path)
        self.state_data = self._load_state()
        self.nodes = []
        self.edges = []
        self.resource_map = {}  # Maps resource addresses to node IDs

    def _load_state(self) -> Dict:
        """Load and parse the Terraform state file."""
        try:
            with open(self.tfstate_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading state file: {e}", file=sys.stderr)
            sys.exit(1)

        # Detect terraform show -json format (has format_version / values.root_module)
        # and normalize it to the terraform state pull format (has top-level resources[])
        if 'format_version' in data and 'values' in data:
            data = self._normalize_show_format(data)

        return data

    def _normalize_show_format(self, data: Dict) -> Dict:
        """Convert terraform show -json format to terraform state pull format."""
        resources = []

        def collect_resources(module: Dict):
            for r in module.get('resources', []):
                resources.append({
                    'mode': r.get('mode', 'managed'),
                    'type': r.get('type', ''),
                    'name': r.get('name', ''),
                    'provider': r.get('provider_name', ''),
                    'instances': [{'attributes': r.get('values', {})}],
                })
            for child in module.get('child_modules', []):
                collect_resources(child)

        collect_resources(data.get('values', {}).get('root_module', {}))

        return {
            'terraform_version': data.get('terraform_version', 'unknown'),
            'serial': 0,
            'resources': resources,
        }

    def _get_resource_address(self, resource: Dict) -> str:
        """Generate a unique address for a resource."""
        mode = resource.get('mode', 'managed')
        rtype = resource.get('type', '')
        name = resource.get('name', '')

        if mode == 'data':
            return f"data.{rtype}.{name}"
        return f"{rtype}.{name}"

    def _get_resource_id(self, resource: Dict, instance_idx: int = 0) -> str:
        """Generate a unique ID for a resource instance."""
        address = self._get_resource_address(resource)
        if instance_idx > 0:
            return f"{address}[{instance_idx}]"
        return address

    def _extract_node_attributes(self, resource: Dict, instance: Dict) -> Dict:
        """Extract relevant attributes from a resource for display."""
        attributes = instance.get('attributes', {})

        # Common attributes to display
        display_attrs = {}

        # ID is usually important
        if 'id' in attributes:
            display_attrs['id'] = attributes['id']

        # Name or display name
        if 'name' in attributes:
            display_attrs['name'] = attributes['name']
        elif 'display_name' in attributes:
            display_attrs['name'] = attributes['display_name']

        # Description
        if 'description' in attributes:
            display_attrs['description'] = attributes['description']

        # Tags (common in AWS/Azure/GCP)
        if 'tags' in attributes and attributes['tags']:
            display_attrs['tags'] = attributes['tags']
        elif 'labels' in attributes and attributes['labels']:
            display_attrs['labels'] = attributes['labels']

        # ARN (AWS)
        if 'arn' in attributes:
            display_attrs['arn'] = attributes['arn']

        # Location/Region
        for location_key in ['region', 'location', 'zone']:
            if location_key in attributes:
                display_attrs[location_key] = attributes[location_key]
                break

        # Provider
        provider = resource.get('provider', '')
        if provider:
            # Extract provider name from full path
            provider_match = re.search(r'provider\[".*?/([^/]+)"\]', provider)
            if provider_match:
                display_attrs['provider'] = provider_match.group(1)

        return display_attrs

    def _find_attribute_references(self, value: Any, current_path: str = "") -> List[str]:
        """
        Recursively search for resource references in attribute values.
        References typically look like: resource_type.resource_name.attribute
        """
        references = []

        if isinstance(value, str):
            # Look for patterns like: aws_vpc.main.id, module.network.vpc_id, etc.
            # This is a simplified heuristic - real references are resolved by Terraform
            pattern = r'\b([a-z_]+\.[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)\b'
            matches = re.findall(pattern, value)
            references.extend(matches)

        elif isinstance(value, dict):
            for k, v in value.items():
                references.extend(self._find_attribute_references(v, f"{current_path}.{k}"))

        elif isinstance(value, list):
            for i, item in enumerate(value):
                references.extend(self._find_attribute_references(item, f"{current_path}[{i}]"))

        return references

    def _extract_dependencies(self, resource: Dict, instance: Dict) -> Set[str]:
        """Extract dependencies from a resource instance."""
        dependencies = set()

        # Explicit dependencies field
        if 'dependencies' in instance:
            dependencies.update(instance['dependencies'])

        # Check for resource references in attributes
        attributes = instance.get('attributes', {})
        refs = self._find_attribute_references(attributes)
        dependencies.update(refs)

        return dependencies

    def _get_resource_color(self, resource_type: str, provider: str) -> str:
        """Assign colors to resources based on type or provider."""
        # Color scheme based on provider
        provider_colors = {
            'aws': '#FF9900',      # AWS Orange
            'azurerm': '#0078D4',  # Azure Blue
            'google': '#4285F4',   # Google Blue
            'okta': '#007DC1',     # Okta Blue
            'kubernetes': '#326CE5',  # K8s Blue
            'helm': '#0F1689',     # Helm Dark Blue
            'datadog': '#632CA6',  # Datadog Purple
            'github': '#24292e',   # GitHub Dark
        }

        # Default color based on provider
        for prov, color in provider_colors.items():
            if prov in provider.lower():
                return color

        # Fallback color scheme by resource category
        if 'network' in resource_type or 'vpc' in resource_type or 'subnet' in resource_type:
            return '#4CAF50'  # Green
        elif 'compute' in resource_type or 'instance' in resource_type or 'vm' in resource_type:
            return '#2196F3'  # Blue
        elif 'storage' in resource_type or 'bucket' in resource_type or 'disk' in resource_type:
            return '#FF9800'  # Orange
        elif 'database' in resource_type or 'db' in resource_type or 'sql' in resource_type:
            return '#9C27B0'  # Purple
        elif 'security' in resource_type or 'iam' in resource_type or 'role' in resource_type:
            return '#F44336'  # Red
        elif 'group' in resource_type or 'user' in resource_type:
            return '#00BCD4'  # Cyan

        # Default gray
        return '#757575'

    def _calculate_node_size(self, resource: Dict, instance: Dict) -> int:
        """Calculate node size based on importance/complexity."""
        base_size = 10

        # Larger for resources with many dependencies
        deps = self._extract_dependencies(resource, instance)
        size = base_size + len(deps) * 2

        # Larger for resources with many attributes
        attrs = instance.get('attributes', {})
        size += len(attrs) * 0.5

        return min(size, 30)  # Cap at 30

    def parse(self) -> Tuple[List[Dict], List[Dict]]:
        """Parse the state file and return nodes and edges."""
        resources = self.state_data.get('resources', [])

        # First pass: Create nodes
        for resource in resources:
            resource_type = resource.get('type', 'unknown')
            resource_name = resource.get('name', 'unknown')
            provider = resource.get('provider', '')
            mode = resource.get('mode', 'managed')

            instances = resource.get('instances', [])

            for idx, instance in enumerate(instances):
                resource_id = self._get_resource_id(resource, idx)
                resource_address = self._get_resource_address(resource)

                # Extract display attributes
                display_attrs = self._extract_node_attributes(resource, instance)

                # Create node
                node = {
                    'id': resource_id,
                    'label': resource_name,
                    'type': resource_type,
                    'mode': mode,
                    'address': resource_address,
                    'provider': provider,
                    'attributes': display_attrs,
                    'color': self._get_resource_color(resource_type, provider),
                    'size': self._calculate_node_size(resource, instance),
                }

                self.nodes.append(node)
                self.resource_map[resource_address] = resource_id

                # Store for dependency resolution
                instance['_resource_id'] = resource_id
                instance['_resource'] = resource

        # Second pass: Create edges from dependencies
        edge_id = 0
        for resource in resources:
            instances = resource.get('instances', [])

            for instance in instances:
                source_id = instance['_resource_id']
                dependencies = self._extract_dependencies(instance['_resource'], instance)

                for dep in dependencies:
                    # Try to resolve dependency to a node ID
                    target_id = self.resource_map.get(dep)

                    if target_id and target_id != source_id:
                        edge = {
                            'id': f"e{edge_id}",
                            'source': source_id,
                            'target': target_id,
                            'type': 'arrow',
                            'size': 2,
                        }
                        self.edges.append(edge)
                        edge_id += 1

        return self.nodes, self.edges

    def generate_graph_data(self) -> Dict:
        """Generate the complete graph data structure."""
        nodes, edges = self.parse()

        # Calculate statistics
        node_types = defaultdict(int)
        for node in nodes:
            node_types[node['type']] += 1

        return {
            'metadata': {
                'terraform_version': self.state_data.get('terraform_version', 'unknown'),
                'serial': self.state_data.get('serial', 0),
                'resource_count': len(nodes),
                'dependency_count': len(edges),
                'resource_types': dict(node_types),
            },
            'nodes': nodes,
            'edges': edges,
        }

    def save_graph(self, output_path: Path):
        """Save the graph data as a JS file to avoid CORS issues when opened locally."""
        graph_data = self.generate_graph_data()

        with open(output_path, 'w') as f:
            f.write('window.GRAPH_DATA = ')
            json.dump(graph_data, f, indent=2)
            f.write(';\n')

        print(f"Graph data saved to: {output_path}")
        print(f"Nodes: {len(graph_data['nodes'])}")
        print(f"Edges: {len(graph_data['edges'])}")
        print(f"Resource types: {list(graph_data['metadata']['resource_types'].keys())}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python tfstate_graph_parser.py <path_to_tfstate> [output_dir]")
        sys.exit(1)

    tfstate_path = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('scripts/tfstate-visualizer')

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse and save
    parser = TerraformStateParser(tfstate_path)
    output_path = output_dir / 'graph-data.js'
    parser.save_graph(output_path)

    print(f"\nTo visualize the graph, open: {output_dir / 'index.html'}")


if __name__ == '__main__':
    main()
