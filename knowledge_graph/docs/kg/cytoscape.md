# Knowledge Graph (Interactive from schema.ttl)

<div class="toolbar">
  <input id="searchBox" placeholder="Search…" />
  <select id="layoutSelect">
    <option value="cose">COSE</option>
    <option value="fcose">fCOSE</option>
    <option value="concentric">Concentric</option>
    <option value="breadthfirst">Breadth-first</option>
    <option value="grid">Grid</option>
  </select>
  <button id="btnFit">Fit</button>
</div>

<div id="cy"></div>

<script>
document.addEventListener('DOMContentLoaded', () => {
  if (typeof KG_ELEMENTS === 'undefined') {
    document.getElementById('cy').innerText = 'KG_ELEMENTS not found. Run the generator.';
    return;
  }
  const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: KG_ELEMENTS,
    wheelSensitivity: 0.2,
    style: [
      { selector: 'node', style: {
        'label': 'data(label)',
        'shape': 'round-rectangle',
        'text-wrap': 'wrap',
        'text-max-width': '160px',
        'padding': '8px', 'font-size': '12px',
        'background-color': '#e3f2fd', 'border-color': '#90caf9', 'border-width': 1
      }},
      { selector: 'node[group = "Datatype"]', style: {
        'background-color': '#fff8e1', 'border-color': '#ffe082'
      }},
      { selector: 'edge', style: {
        'label': 'data(label)',
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'line-color': '#b0bec5', 'target-arrow-color': '#b0bec5',
        'font-size': '10px',
        'text-background-color': '#fff',
        'text-background-opacity': 0.85,
        'text-background-padding': 2
      }},
      { selector: 'edge.subclass', style: { 'line-style': 'dashed', 'opacity': 0.6 } },
      { selector: ':selected', style: {
        'border-width': 3, 'border-color': '#1565c0',
        'line-color': '#1565c0', 'target-arrow-color': '#1565c0'
      }},
      { selector: '.faded', style: { 'opacity': 0.15 } }
    ],
    layout: { name: 'cose', animate: false, idealEdgeLength: 140, nodeRepulsion: 8000 }
  });

  const fit = () => cy.fit(cy.elements(), 30);
  fit();

  document.getElementById('btnFit').onclick = fit;
  document.getElementById('layoutSelect').onchange = e =>
    cy.layout({ name: e.target.value, animate: false, idealEdgeLength: 140, nodeRepulsion: 8000 }).run();

  const box = document.getElementById('searchBox');
  let last = '';
  const clear = () => { cy.elements().removeClass('faded'); last=''; };
  box.addEventListener('input', () => {
    const q = box.value.trim().toLowerCase();
    if (!q) return clear();
    const matches = cy.nodes().filter(n => {
      const d = n.data();
      return [d.id, d.label, d.qname, d.group].filter(Boolean).some(x => String(x).toLowerCase().includes(q));
    });
    cy.elements().addClass('faded');
    matches.removeClass('faded'); matches.connectedEdges().removeClass('faded');
    matches.connectedEdges().connectedNodes().removeClass('faded');
    if (q !== last && matches.nonempty()) cy.animate({ fit: { eles: matches, padding: 50 }, duration: 200 });
    last = q;
  });

  cy.on('tap', 'node', e => cy.animate({ fit: { eles: e.target.closedNeighborhood(), padding: 60 }, duration: 200 }));
});
</script>
