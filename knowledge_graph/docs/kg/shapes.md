
```markdown
# SHACL Shapes (Authoritative)

Below are the SHACL shapes enforcing the modeling choices above (directly integrated; no extra properties section). This matches the PDF’s predicates and cardinalities (e.g., optional `schema:title`, snippet via `schema:abstract`, block-level `aql:rawContent`/`aql:xPath`, explicit Memento URLs, provider multi-paths). :contentReference[oaicite:12]{index=12}

```turtle
@prefix aql:   <https://aql.webis.de/> .
@prefix schema:<http://schema.org/> .
@prefix dct:   <http://purl.org/dc/terms/> .
@prefix owl:   <http://www.w3.org/2002/07/owl#> .
@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos:  <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix http:  <https://www.w3.org/2011/http#> .
@prefix sh:    <http://www.w3.org/ns/shacl#> .

aql:SERPShape a sh:NodeShape ;
  sh:targetClass aql:SERP ;
  sh:property [ sh:path schema:identifier ; sh:datatype xsd:string ; sh:minCount 1 ] ;
  sh:property [ sh:path schema:name ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:trecTaskURL ; sh:datatype xsd:anyURI ] ;
  sh:property [ sh:path schema:hasPart ; sh:class aql:ResultBlock ; sh:nodeKind sh:IRI ; sh:minCount 1 ] ;
  sh:property [ sh:path schema:isBasedOn ; sh:class aql:Capture ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path schema:provider ; sh:class aql:Provider ; sh:nodeKind sh:IRI ; sh:minCount 1 ] ;
  sh:property [ sh:path schema:archivedAt ; sh:class aql:Archive ; sh:nodeKind sh:IRI ] .

aql:ResultBlockShape a sh:NodeShape ;
  sh:targetClass aql:ResultBlock ;
  sh:property [ sh:path schema:isPartOf ; sh:class aql:SERP ; sh:nodeKind sh:IRI ; sh:minCount 1 ] ;
  sh:property [ sh:path schema:title ; sh:datatype xsd:string ] ;           # optional
  sh:property [ sh:path schema:abstract ; sh:datatype xsd:string ] ;        # snippet
  sh:property [ sh:path aql:rank ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path aql:xPath ; sh:datatype xsd:string ] ;              # XPath of entire block
  sh:property [ sh:path aql:rawContent ; sh:datatype xsd:string ] ;         # raw serialized block
  sh:property [
    sh:path aql:resultBlockType ; sh:datatype xsd:string ;
    sh:in ( "web_result" "direct_answer" "ai_overview" "knowledge_panel"
            "local_pack" "image_pack" "video_pack" "top_stories"
            "shopping" "people_also_ask" "jobs" "events" )
  ] .

aql:WebSearchResultBlockShape a sh:NodeShape ;
  sh:targetClass aql:WebSearchResultBlock ;
  sh:node aql:ResultBlockShape .

aql:SpecialContentResultBlockShape a sh:NodeShape ;
  sh:targetClass aql:SpecialContentResultBlock ;
  sh:node aql:ResultBlockShape .

aql:ResultShape a sh:NodeShape ;
  sh:targetClass aql:Result ;
  sh:property [ sh:path schema:isBasedOn ; sh:class aql:Capture ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path schema:identifier ; sh:datatype xsd:string ] ;
  sh:property [ sh:path schema:title ; sh:datatype xsd:string ] ;
  sh:property [ sh:path schema:url ; sh:datatype xsd:anyURI ] .

aql:CaptureShape a sh:NodeShape ;
  sh:targetClass aql:Capture ;
  sh:property [ sh:path aql:digest ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:mementoAPIViewerURL ; sh:datatype xsd:anyURI ] ;
  sh:property [ sh:path aql:mementoAPIRawURL ; sh:datatype xsd:anyURI ] ;
  sh:property [ sh:path schema:dateCreated ; sh:datatype xsd:dateTime ] ;
  sh:property [ sh:path schema:url ; sh:datatype xsd:anyURI ] ;
  sh:property [ sh:path http:statusCodeNumber ; sh:datatype xsd:integer ] ;
  sh:property [ sh:path schema:encodingFormat ; sh:datatype xsd:string ] ;
  sh:property [ sh:path dct:isPartOf ; sh:class aql:SERP ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path schema:isBasedOn ; sh:class aql:Archive ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path dct:source ; sh:class aql:Capture ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path dct:relation ; sh:class aql:Capture ; sh:nodeKind sh:IRI ] ;
  sh:property [ sh:path schema:mainEntity ; sh:class aql:Result ; sh:nodeKind sh:IRI ] .

aql:ProviderShape a sh:NodeShape ;
  sh:targetClass aql:Provider ;
  sh:property [ sh:path schema:identifier ; sh:datatype xsd:string ; sh:minCount 1 ] ;
  sh:property [ sh:path schema:name ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:domain ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:hostname ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:urlPathPrefix ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:urlPathTemplate ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:urlPath ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:path ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:wikiDataURL ; sh:datatype xsd:anyURI ] .

aql:ArchiveShape a sh:NodeShape ;
  sh:targetClass aql:Archive ;
  sh:property [ sh:path schema:identifier ; sh:datatype xsd:string ; sh:minCount 1 ] ;
  sh:property [ sh:path schema:name ; sh:datatype xsd:string ] ;
  sh:property [ sh:path aql:mementoAPIBaseURL ; sh:datatype xsd:anyURI ] ;
  sh:property [ sh:path aql:cdxAPIBaseURL ; sh:datatype xsd:anyURI ] ;
  sh:property [ sh:path aql:wikiDataURL ; sh:datatype xsd:anyURI ] .
```
---
