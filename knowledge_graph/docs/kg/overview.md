# AQL Knowledge Graph – Overview

This page summarizes the entities and their key relations as used in AQL.

**Core classes**
- `aql:SERP` (subClassOf `dct:Collection`): groups result blocks; links to provider/archive/captures. :contentReference[oaicite:1]{index=1}
- `aql:ResultBlock` (subClassOf `schema:CreativeWork`, `schema:ListItem`): represents an **entire** SERP block; has XPath, **raw block content**, rank, and a **resultBlockType** label. `schema:title` optional; snippet via `schema:abstract`. :contentReference[oaicite:2]{index=2}
- `aql:WebSearchResultBlock` / `aql:SpecialContentResultBlock`: subclasses for organic vs. featured/direct-answer blocks. :contentReference[oaicite:3]{index=3}
- `aql:Result` (subClassOf `schema:WebPage`): the landing page. :contentReference[oaicite:4]{index=4}
- `aql:Capture` (subClassOf `schema:WebPage`): with HTTP/MIME, timestamp, **Memento viewer + raw URLs**. :contentReference[oaicite:5]{index=5}
- `aql:Provider` (subClassOf `schema:Service`): domain/hostname and **multiple** path variants (`aql:urlPathPrefix`, `aql:urlPathTemplate`, `aql:urlPath`, `aql:path`), optional Wikidata link. :contentReference[oaicite:6]{index=6}
- `aql:Archive` (subClassOf `schema:ArchiveOrganization`): CDX/Memento base URLs, optional Wikidata link. :contentReference[oaicite:7]{index=7}

**Key modeling specifics (from the PDF)**
- Result block **raw capture** at block level: `aql:rawContent` for the **entire** block; `aql:xPath` of the **entire** block. :contentReference[oaicite:8]{index=8}
- `aql:resultBlockType` controlled labels (e.g., `web_result`, `direct_answer`, `ai_overview`, `knowledge_panel`, `local_pack`, `image_pack`, `video_pack`, `top_stories`, `shopping`, `people_also_ask`, `jobs`, `events`). :contentReference[oaicite:9]{index=9}
- Memento endpoints modeled explicitly on `aql:Capture`: `aql:mementoAPIViewerURL`, `aql:mementoAPIRawURL`. :contentReference[oaicite:10]{index=10}

