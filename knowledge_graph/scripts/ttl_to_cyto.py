#!/usr/bin/env python3
from pathlib import Path
from rdflib import Graph, RDF, RDFS, OWL, Namespace
import json

BASE = Path(__file__).resolve().parents[1]
TTL  = BASE / "docs" / "kg" / "schema.ttl"             # <- adjust if needed
OUT  = BASE / "docs" / "js" / "kg-elements.js"
OUT.parent.mkdir(parents=True, exist_ok=True)

SH = Namespace("http://www.w3.org/ns/shacl#")

g = Graph()
g.parse(TTL)

def qn(uri):
    try:
        return g.namespace_manager.normalizeUri(uri)
    except Exception:
        return str(uri)

# --- collect classes (RDFS/OWL) ---
classes = set(g.subjects(RDF.type, RDFS.Class)) | set(g.subjects(RDF.type, OWL.Class))
nodes = {}
def touch_node(uri, group="Class", label=None):
    _id = str(uri)
    if _id not in nodes:
        rdfs_label = g.value(uri, RDFS.label)
        name = label or (str(rdfs_label) if rdfs_label else qn(uri))
        nodes[_id] = {
            "data": {"id": _id, "label": name, "qname": qn(uri), "group": group}
        }

for c in classes:
    touch_node(c, "Class")

# --- collect properties (RDFS/OWL) and domain/range edges ---
props = set(g.subjects(RDF.type, RDF.Property)) | \
        set(g.subjects(RDF.type, OWL.ObjectProperty)) | \
        set(g.subjects(RDF.type, OWL.DatatypeProperty))

edges = {}
def add_edge(src, prop, dst):
    sid = str(src); pid = str(prop); did = str(dst)
    if sid == "None" or did == "None":
        return
    eid = f"{sid}|{pid}|{did}"
    if eid in edges: return
    # ensure nodes exist
    touch_node(src)
    touch_node(dst)
    label = qn(prop)
    edges[eid] = {
        "data": {"id": eid, "source": sid, "target": did, "label": label, "prop": qn(prop)}
    }

for p in props:
    dom = g.value(p, RDFS.domain)
    rng = g.value(p, RDFS.range)
    # datatype ranges become their own node group
    if rng and (str(rng).startswith("http://www.w3.org/2001/XMLSchema#")):
        touch_node(rng, "Datatype", label=qn(rng))
    if dom and rng:
        add_edge(dom, p, rng)

# --- SHACL: class→(sh:path)→class/datatype from NodeShapes ---
for shape in g.subjects(RDF.type, SH.NodeShape):
    target_class = g.value(shape, SH.targetClass)
    if not target_class:
        continue
    touch_node(target_class, "Class")
    # property shapes: either inline blank nodes or linked via sh:property
    for pshape in g.objects(shape, SH.property):
        path = g.value(pshape, SH.path)               # property IRI
        pclass = g.value(pshape, SH["class"])         # object class
        pdatatype = g.value(pshape, SH.datatype)      # xsd datatype
        if path and pclass:
            touch_node(pclass, "Class")
            add_edge(target_class, path, pclass)
        if path and pdatatype:
            # ensure datatype node exists and is marked
            touch_node(pdatatype, "Datatype", label=qn(pdatatype))
            add_edge(target_class, path, pdatatype)

# Optional: show rdfs:subClassOf edges (light grey)
for child, _, parent in g.triples((None, RDFS.subClassOf, None)):
    if child in classes or parent in classes:
        touch_node(child, "Class"); touch_node(parent, "Class")
        eid = f"{child}|subClassOf|{parent}"
        edges[eid] = {
            "data": {"id": eid, "source": str(child), "target": str(parent), "label": "subClassOf"},
            "classes": "subclass"
        }

# Build Cytoscape element lists
els = {
    "nodes": list(nodes.values()),
    "edges": list(edges.values())
}

OUT.write_text("const KG_ELEMENTS = " + json.dumps(els, ensure_ascii=False) + ";\n", encoding="utf-8")
print(f"Wrote {OUT} with {len(nodes)} nodes and {len(edges)} edges.")
