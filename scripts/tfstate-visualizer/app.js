/**
 * Terraform State Network Graph Visualizer
 *
 * Main application logic for visualizing Terraform state files
 * using Sigma.js for network graph rendering.
 */

class TerraformGraphVisualizer {
    constructor() {
        this.graph = null;
        this.renderer = null;
        this.graphData = null;
        this.hoveredNode = null;
        this.selectedNode = null;
        this.searchResults = [];
        this.showLabels = true;

        // DOM elements
        this.elements = {
            graph: document.getElementById('graph'),
            tooltip: document.getElementById('tooltip'),
            loading: document.getElementById('loading'),
            error: document.getElementById('error'),
            searchInput: document.getElementById('search-input'),
            searchResults: document.getElementById('search-results'),
            searchList: document.getElementById('search-list'),
            searchCount: document.getElementById('search-count'),
            legend: document.getElementById('legend'),
            legendContent: document.getElementById('legend-content'),
            infoPanel: document.getElementById('info-panel'),
            minimap: document.getElementById('minimap'),
            minimapCanvas: document.getElementById('minimap-canvas'),
        };

        // State
        this.state = {
            camera: { x: 0, y: 0, ratio: 1 },
            highlightedNodes: new Set(),
        };

        this.init();
    }

    async init() {
        try {
            // Load graph data
            this.loadGraphData();

            // Initialize the graph
            this.initializeGraph();

            // Setup event listeners
            this.setupEventListeners();

            // Initialize minimap
            this.initializeMinimap();

            // Build legend
            this.buildLegend();

            // Hide loading
            this.elements.loading.style.display = 'none';

            // Initial layout animation
            this.animateLayout();

        } catch (error) {
            this.showError(error.message);
        }
    }

    loadGraphData() {
        if (!window.GRAPH_DATA) {
            throw new Error('Graph data not found. Please run the parser script first.');
        }
        this.graphData = window.GRAPH_DATA;

        // Update stats
        document.getElementById('node-count').textContent = `Nodes: ${this.graphData.nodes.length}`;
        document.getElementById('edge-count').textContent = `Edges: ${this.graphData.edges.length}`;
        document.getElementById('tf-version').textContent = `Terraform: ${this.graphData.metadata.terraform_version}`;
    }

    initializeGraph() {
        // Create a new graph
        this.graph = new graphology.Graph();

        // Add nodes
        this.graphData.nodes.forEach(node => {
            this.graph.addNode(node.id, {
                label: node.label,
                size: node.size,
                color: node.color,
                type: 'circle',
                resourceType: node.type,
                mode: node.mode,
                address: node.address,
                provider: node.provider,
                attributes: node.attributes,
                x: Math.random() * 100,
                y: Math.random() * 100,
            });
        });

        // Add edges
        this.graphData.edges.forEach(edge => {
            if (this.graph.hasNode(edge.source) && this.graph.hasNode(edge.target)) {
                this.graph.addEdge(edge.source, edge.target, {
                    size: edge.size || 1,
                    color: '#475569',
                    type: 'arrow',
                });
            }
        });

        // Apply initial layout
        this.applyLayout();

        // Initialize Sigma renderer
        this.renderer = new Sigma(this.graph, this.elements.graph, {
            renderEdgeLabels: false,
            enableEdgeEvents: false,
            defaultNodeType: 'circle',
            defaultEdgeType: 'arrow',
            labelFont: 'Inter, system-ui, sans-serif',
            labelSize: 12,
            labelWeight: '500',
            labelColor: { color: '#F1F5F9' },
        });
    }

    applyLayout() {
        const nodes = this.graph.nodes();
        const count = nodes.length;
        nodes.forEach((node, i) => {
            const angle = (2 * Math.PI * i) / count;
            this.graph.setNodeAttribute(node, 'x', Math.cos(angle));
            this.graph.setNodeAttribute(node, 'y', Math.sin(angle));
        });
    }

    animateLayout() {
        this.renderer.refresh();
    }

    setupEventListeners() {
        // Hover events
        this.renderer.on('enterNode', ({ node }) => {
            this.hoveredNode = node;
            this.showTooltip(node);

            // Highlight connected nodes
            this.highlightConnectedNodes(node);
        });

        this.renderer.on('leaveNode', () => {
            this.hoveredNode = null;
            this.hideTooltip();
            this.clearHighlight();
        });

        // Click events
        this.renderer.on('clickNode', ({ node }) => {
            this.selectNode(node);
        });

        this.renderer.on('clickStage', () => {
            this.deselectNode();
        });

        // Mouse move for tooltip positioning
        this.renderer.getMouseCaptor().on('mousemove', (event) => {
            if (this.hoveredNode) {
                this.positionTooltip(event.x, event.y);
            }
        });

        // Camera events for minimap
        this.renderer.getCamera().on('updated', () => {
            this.updateMinimap();
        });

        // Search
        this.elements.searchInput.addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });

        document.getElementById('clear-search').addEventListener('click', () => {
            this.clearSearch();
        });

        // Control buttons
        document.getElementById('reset-view').addEventListener('click', () => {
            this.resetView();
        });

        document.getElementById('toggle-labels').addEventListener('click', () => {
            this.toggleLabels();
        });

        document.getElementById('toggle-legend').addEventListener('click', () => {
            this.toggleLegend();
        });

        document.getElementById('export-btn').addEventListener('click', () => {
            this.exportAsImage();
        });

        document.getElementById('close-info').addEventListener('click', () => {
            this.deselectNode();
        });

        document.getElementById('retry-btn').addEventListener('click', () => {
            window.location.reload();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.clearSearch();
                this.deselectNode();
            } else if (e.key === '/' && !this.isInputFocused()) {
                e.preventDefault();
                this.elements.searchInput.focus();
            } else if (e.key === 'r' && !this.isInputFocused()) {
                this.resetView();
            } else if (e.key === 'l' && !this.isInputFocused()) {
                this.toggleLabels();
            }
        });
    }

    highlightConnectedNodes(nodeId) {
        const connectedNodes = new Set([nodeId]);

        // Get neighbors
        this.graph.forEachNeighbor(nodeId, (neighbor) => {
            connectedNodes.add(neighbor);
        });

        // Dim non-connected nodes
        this.graph.forEachNode((node) => {
            if (!connectedNodes.has(node)) {
                this.graph.setNodeAttribute(node, 'color', this.dimColor(
                    this.graph.getNodeAttribute(node, 'originalColor') ||
                    this.graph.getNodeAttribute(node, 'color')
                ));
            } else {
                // Store original color
                if (!this.graph.getNodeAttribute(node, 'originalColor')) {
                    this.graph.setNodeAttribute(node, 'originalColor',
                        this.graph.getNodeAttribute(node, 'color'));
                }
            }
        });

        // Dim non-connected edges
        this.graph.forEachEdge((edge, attrs, source, target) => {
            if (!connectedNodes.has(source) || !connectedNodes.has(target)) {
                this.graph.setEdgeAttribute(edge, 'color', '#1E293B');
            }
        });

        this.renderer.refresh();
    }

    clearHighlight() {
        // Restore original colors
        this.graph.forEachNode((node) => {
            const originalColor = this.graph.getNodeAttribute(node, 'originalColor');
            if (originalColor) {
                this.graph.setNodeAttribute(node, 'color', originalColor);
            }
        });

        this.graph.forEachEdge((edge) => {
            this.graph.setEdgeAttribute(edge, 'color', '#475569');
        });

        this.renderer.refresh();
    }

    dimColor(color) {
        // Simple dimming by reducing opacity
        return color + '40'; // Add alpha
    }

    showTooltip(nodeId) {
        const node = this.graph.getNodeAttributes(nodeId);

        document.getElementById('tooltip-type').textContent = node.resourceType;
        document.getElementById('tooltip-mode').textContent = node.mode;
        document.getElementById('tooltip-label').textContent = node.label;

        // Build attributes HTML
        const content = [];
        if (node.attributes && Object.keys(node.attributes).length > 0) {
            for (const [key, value] of Object.entries(node.attributes)) {
                if (typeof value === 'object') {
                    content.push(`
                        <div class="attribute">
                            <span class="attribute-key">${key}:</span>
                            <span class="attribute-value">${JSON.stringify(value)}</span>
                        </div>
                    `);
                } else {
                    content.push(`
                        <div class="attribute">
                            <span class="attribute-key">${key}:</span>
                            <span class="attribute-value">${value}</span>
                        </div>
                    `);
                }
            }
        } else {
            content.push('<div class="attribute"><span class="attribute-value">No additional attributes</span></div>');
        }

        document.getElementById('tooltip-content').innerHTML = content.join('');
        this.elements.tooltip.style.display = 'block';
    }

    hideTooltip() {
        this.elements.tooltip.style.display = 'none';
    }

    positionTooltip(x, y) {
        const tooltip = this.elements.tooltip;
        const offset = 15;

        let left = x + offset;
        let top = y + offset;

        // Keep tooltip in viewport
        const rect = tooltip.getBoundingClientRect();
        if (left + rect.width > window.innerWidth) {
            left = x - rect.width - offset;
        }
        if (top + rect.height > window.innerHeight) {
            top = y - rect.height - offset;
        }

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
    }

    selectNode(nodeId) {
        this.selectedNode = nodeId;
        const node = this.graph.getNodeAttributes(nodeId);

        // Show info panel
        document.getElementById('info-title').textContent = `${node.resourceType}.${node.label}`;

        const sections = [];

        // Basic info
        sections.push(`
            <div class="info-section">
                <h4>Basic Information</h4>
                <div class="info-attributes">
                    <div class="info-attribute">
                        <div class="info-attribute-key">Type</div>
                        <div class="info-attribute-value">${node.resourceType}</div>
                    </div>
                    <div class="info-attribute">
                        <div class="info-attribute-key">Mode</div>
                        <div class="info-attribute-value">${node.mode}</div>
                    </div>
                    <div class="info-attribute">
                        <div class="info-attribute-key">Address</div>
                        <div class="info-attribute-value">${node.address}</div>
                    </div>
                    <div class="info-attribute">
                        <div class="info-attribute-key">Provider</div>
                        <div class="info-attribute-value">${node.provider}</div>
                    </div>
                </div>
            </div>
        `);

        // Attributes
        if (node.attributes && Object.keys(node.attributes).length > 0) {
            const attrs = Object.entries(node.attributes).map(([key, value]) => `
                <div class="info-attribute">
                    <div class="info-attribute-key">${key}</div>
                    <div class="info-attribute-value">${
                        typeof value === 'object' ? JSON.stringify(value, null, 2) : value
                    }</div>
                </div>
            `).join('');

            sections.push(`
                <div class="info-section">
                    <h4>Attributes</h4>
                    <div class="info-attributes">
                        ${attrs}
                    </div>
                </div>
            `);
        }

        // Dependencies
        const inbound = [];
        const outbound = [];

        this.graph.forEachInNeighbor(nodeId, (neighbor) => {
            inbound.push(neighbor);
        });

        this.graph.forEachOutNeighbor(nodeId, (neighbor) => {
            outbound.push(neighbor);
        });

        if (inbound.length > 0 || outbound.length > 0) {
            sections.push(`
                <div class="info-section">
                    <h4>Dependencies</h4>
                    ${inbound.length > 0 ? `
                        <div class="info-attribute">
                            <div class="info-attribute-key">Depends On (${inbound.length})</div>
                            <div class="info-attribute-value">${inbound.join(', ')}</div>
                        </div>
                    ` : ''}
                    ${outbound.length > 0 ? `
                        <div class="info-attribute">
                            <div class="info-attribute-key">Used By (${outbound.length})</div>
                            <div class="info-attribute-value">${outbound.join(', ')}</div>
                        </div>
                    ` : ''}
                </div>
            `);
        }

        document.getElementById('info-content').innerHTML = sections.join('');
        this.elements.infoPanel.style.display = 'flex';
        this.elements.searchResults.style.display = 'none';
    }

    deselectNode() {
        this.selectedNode = null;
        this.elements.infoPanel.style.display = 'none';
    }

    handleSearch(query) {
        if (!query.trim()) {
            this.clearSearch();
            return;
        }

        const lowerQuery = query.toLowerCase();
        this.searchResults = [];

        // Search in nodes
        this.graph.forEachNode((node, attrs) => {
            const matches =
                attrs.label.toLowerCase().includes(lowerQuery) ||
                attrs.resourceType.toLowerCase().includes(lowerQuery) ||
                attrs.address.toLowerCase().includes(lowerQuery) ||
                node.toLowerCase().includes(lowerQuery);

            if (matches) {
                this.searchResults.push(node);
            }
        });

        this.displaySearchResults();
    }

    displaySearchResults() {
        if (this.searchResults.length === 0) {
            this.elements.searchResults.style.display = 'none';
            this.clearHighlight();
            return;
        }

        // Update count
        this.elements.searchCount.textContent = `${this.searchResults.length} result${this.searchResults.length !== 1 ? 's' : ''}`;

        // Build results list
        const items = this.searchResults.map(nodeId => {
            const attrs = this.graph.getNodeAttributes(nodeId);
            return `
                <div class="search-result-item" data-node="${nodeId}">
                    <div class="search-result-label">${attrs.label}</div>
                    <div class="search-result-type">${attrs.resourceType} (${attrs.mode})</div>
                </div>
            `;
        }).join('');

        this.elements.searchList.innerHTML = items;
        this.elements.searchResults.style.display = 'flex';

        // Add click handlers
        this.elements.searchList.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const nodeId = item.getAttribute('data-node');
                this.focusOnNode(nodeId);
                this.selectNode(nodeId);
            });
        });

        // Highlight search results
        this.highlightSearchResults();
    }

    highlightSearchResults() {
        const highlighted = new Set(this.searchResults);

        this.graph.forEachNode((node) => {
            if (!highlighted.has(node)) {
                this.graph.setNodeAttribute(node, 'color', this.dimColor(
                    this.graph.getNodeAttribute(node, 'originalColor') ||
                    this.graph.getNodeAttribute(node, 'color')
                ));
            } else {
                if (!this.graph.getNodeAttribute(node, 'originalColor')) {
                    this.graph.setNodeAttribute(node, 'originalColor',
                        this.graph.getNodeAttribute(node, 'color'));
                }
                // Make highlighted nodes more prominent
                this.graph.setNodeAttribute(node, 'size',
                    (this.graph.getNodeAttribute(node, 'originalSize') ||
                     this.graph.getNodeAttribute(node, 'size')) * 1.5
                );
            }
        });

        this.renderer.refresh();
    }

    clearSearch() {
        this.elements.searchInput.value = '';
        this.searchResults = [];
        this.elements.searchResults.style.display = 'none';

        // Restore node sizes
        this.graph.forEachNode((node) => {
            const originalSize = this.graph.getNodeAttribute(node, 'originalSize');
            if (originalSize) {
                this.graph.setNodeAttribute(node, 'size', originalSize);
            }
        });

        this.clearHighlight();
    }

    focusOnNode(nodeId) {
        const nodePosition = this.renderer.getNodeDisplayData(nodeId);
        if (nodePosition) {
            this.renderer.getCamera().animate(
                { x: nodePosition.x, y: nodePosition.y, ratio: 0.5 },
                { duration: 600 }
            );
        }
    }

    resetView() {
        this.renderer.getCamera().animate(
            { x: 0.5, y: 0.5, ratio: 1 },
            { duration: 600 }
        );
        this.clearSearch();
        this.deselectNode();
    }

    toggleLabels() {
        this.showLabels = !this.showLabels;
        this.renderer.setSetting('renderLabels', this.showLabels);
        this.renderer.refresh();
    }

    toggleLegend() {
        const legend = this.elements.legend;
        legend.style.display = legend.style.display === 'none' ? 'block' : 'none';
    }

    buildLegend() {
        const typeColors = {};

        this.graph.forEachNode((node, attrs) => {
            if (!typeColors[attrs.resourceType]) {
                typeColors[attrs.resourceType] = {
                    color: attrs.originalColor || attrs.color,
                    count: 0,
                };
            }
            typeColors[attrs.resourceType].count++;
        });

        const items = Object.entries(typeColors)
            .sort((a, b) => b[1].count - a[1].count)
            .map(([type, data]) => `
                <div class="legend-item">
                    <div class="legend-color" style="background-color: ${data.color}"></div>
                    <span class="legend-label">${type}</span>
                    <span class="legend-count">${data.count}</span>
                </div>
            `).join('');

        this.elements.legendContent.innerHTML = items;
    }

    _getMinimapTransform() {
        const rect = this.elements.minimap.getBoundingClientRect();
        const padding = 10;
        const drawWidth = rect.width - padding * 2;
        const drawHeight = rect.height - padding * 2;

        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        this.graph.forEachNode((node, attrs) => {
            minX = Math.min(minX, attrs.x); maxX = Math.max(maxX, attrs.x);
            minY = Math.min(minY, attrs.y); maxY = Math.max(maxY, attrs.y);
        });

        const rangeX = maxX - minX || 1;
        const rangeY = maxY - minY || 1;
        const scale = Math.min(drawWidth / rangeX, drawHeight / rangeY);
        const offsetX = padding + (drawWidth - rangeX * scale) / 2;
        const offsetY = padding + (drawHeight - rangeY * scale) / 2;

        return { minX, minY, maxY, scale, offsetX, offsetY };
    }

    _graphToMinimap({ x, y }, transform) {
        const { minX, maxY, scale, offsetX, offsetY } = transform;
        return {
            x: (x - minX) * scale + offsetX,
            y: (maxY - y) * scale + offsetY,
        };
    }

    _minimapToGraph({ x, y }, transform) {
        const { minX, maxY, scale, offsetX, offsetY } = transform;
        return {
            x: (x - offsetX) / scale + minX,
            y: maxY - (y - offsetY) / scale,
        };
    }

    initializeMinimap() {
        const canvas = this.elements.minimapCanvas;
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;

        const rect = this.elements.minimap.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        canvas.style.width = `${rect.width}px`;
        canvas.style.height = `${rect.height}px`;
        ctx.scale(dpr, dpr);

        let isDragging = false;

        canvas.addEventListener('mousedown', (e) => {
            isDragging = true;
            const canvasRect = canvas.getBoundingClientRect();
            const coords = this._minimapToGraph(
                { x: e.clientX - canvasRect.left, y: e.clientY - canvasRect.top },
                this._getMinimapTransform()
            );
            this.renderer.getCamera().animate(coords, { duration: 200 });
        });

        canvas.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const canvasRect = canvas.getBoundingClientRect();
            const coords = this._minimapToGraph(
                { x: e.clientX - canvasRect.left, y: e.clientY - canvasRect.top },
                this._getMinimapTransform()
            );
            this.renderer.getCamera().setState({ ...this.renderer.getCamera().getState(), ...coords });
        });

        canvas.addEventListener('mouseup', () => { isDragging = false; });
        canvas.addEventListener('mouseleave', () => { isDragging = false; });

        this.updateMinimap();
    }

    updateMinimap() {
        const canvas = this.elements.minimapCanvas;
        const ctx = canvas.getContext('2d');
        const rect = this.elements.minimap.getBoundingClientRect();

        ctx.clearRect(0, 0, rect.width, rect.height);

        const transform = this._getMinimapTransform();
        if (!isFinite(transform.minX)) return;

        // Draw edges
        ctx.strokeStyle = '#475569';
        ctx.lineWidth = 0.5;
        this.graph.forEachEdge((edge, attrs, source, target) => {
            const s = this._graphToMinimap(this.graph.getNodeAttributes(source), transform);
            const t = this._graphToMinimap(this.graph.getNodeAttributes(target), transform);
            ctx.beginPath();
            ctx.moveTo(s.x, s.y);
            ctx.lineTo(t.x, t.y);
            ctx.stroke();
        });

        // Draw nodes
        this.graph.forEachNode((node, attrs) => {
            const p = this._graphToMinimap(attrs, transform);
            ctx.fillStyle = attrs.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
            ctx.fill();
        });

        // Draw viewport rectangle using Sigma's coordinate conversion
        try {
            const containerRect = this.elements.graph.getBoundingClientRect();
            const topLeft = this.renderer.viewportToGraph({ x: 0, y: 0 });
            const bottomRight = this.renderer.viewportToGraph({ x: containerRect.width, y: containerRect.height });
            const tl = this._graphToMinimap(topLeft, transform);
            const br = this._graphToMinimap(bottomRight, transform);
            ctx.strokeStyle = '#F59E0B';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(tl.x, tl.y, br.x - tl.x, br.y - tl.y);
        } catch (e) { /* ignore if renderer not ready */ }
    }

    exportAsImage() {
        // Get the current view
        const { width, height } = this.elements.graph.getBoundingClientRect();

        // Create a temporary canvas
        const canvas = document.createElement('canvas');
        canvas.width = width * 2; // 2x for better quality
        canvas.height = height * 2;

        const ctx = canvas.getContext('2d');
        ctx.scale(2, 2);

        // Fill background
        ctx.fillStyle = '#0F172A';
        ctx.fillRect(0, 0, width, height);

        // Get the camera state
        const camera = this.renderer.getCamera();

        // Draw graph (simplified - just nodes and edges)
        this.graph.forEachEdge((edge, attrs, source, target) => {
            const sourcePos = this.renderer.getNodeDisplayData(source);
            const targetPos = this.renderer.getNodeDisplayData(target);

            ctx.strokeStyle = attrs.color;
            ctx.lineWidth = attrs.size || 1;
            ctx.beginPath();
            ctx.moveTo(sourcePos.x, sourcePos.y);
            ctx.lineTo(targetPos.x, targetPos.y);
            ctx.stroke();
        });

        this.graph.forEachNode((node, attrs) => {
            const pos = this.renderer.getNodeDisplayData(node);

            ctx.fillStyle = attrs.color;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, attrs.size, 0, Math.PI * 2);
            ctx.fill();
        });

        // Download
        canvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `terraform-graph-${Date.now()}.png`;
            a.click();
            URL.revokeObjectURL(url);
        });
    }

    showError(message) {
        document.getElementById('error-message').textContent = message;
        this.elements.error.style.display = 'block';
        this.elements.loading.style.display = 'none';
    }

    isInputFocused() {
        return document.activeElement.tagName === 'INPUT' ||
               document.activeElement.tagName === 'TEXTAREA';
    }
}

// Initialize the visualizer when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new TerraformGraphVisualizer();
});
