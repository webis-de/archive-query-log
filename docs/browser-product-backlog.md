# AQL Browser Product Backlog

Links to consider:

- [AQL Paper](https://webis.de/publications.html?q=Archive+Query+Log#reimer_2023)
- [AQL repository](https://webis.de/publications.html?q=Archive+Query+Log#reimer_2023)
- [Lukas' AQL Browser demo](https://aql-browser.web.webis.de/)
- [SWEP GitLab project](https://git.uni-jena.de/fusion/teaching/project/2025wise/swep/aql-browser)
- [SWEP AQL repository fork](https://git.uni-jena.de/fusion/teaching/project/2025wise/swep/aql-browser/archive-query-log)

Glossary:

- SERP: Search engine results page

## Epics

### Epic: View specific AQL data

This epic covers the functionality to view individual archived SERPs, search providers, and web archives in detail, by their ID.

#### Use case: View basic SERP metadata

As a researcher, I want to see the metadata (e.g., original URL, time of archival, query text) of a specific archived SERP so that I can understand the context in which a SERP has been archived.
This could be a header toolbar similar to the one on ChatNoir when [viewing a specific web page](https://chatnoir-webcontent.chatnoir.eu/?index=cw22&uuid=mC8VAylgVOCX_60h9sXS0Q&minimal).

#### Use case: "Unbranded" view of SERP contents

As a researcher, I want to see the parsed contents (i.e., the parsed query and result blocks) of a specific archived SERP in an "unbranded", unified view, i.e., the same UI for any SERP in the AQL, regardless of the search provider, so that I can analyze search results without distractions.

#### Use case: Web archive snapshot preview of SERP

As a researcher, I want to see a preview (e.g., an iframe) of the web archive snapshot of a specific archived SERP, so that I do not have to leave the AQL browser.

#### Use case: Switch between different views of SERP

As a researcher, I want to easily switch between different views of a specific archived SERP, e.g., between an "unbranded" view and a web archive snapshot view, e.g., via tabs, so that I can get a broad understanding of a SERP.
(This could look similar to switching between "plain text" and "full HTML" on [ChatNoir](https://chatnoir-webcontent.chatnoir.eu/?index=cw22&uuid=mC8VAylgVOCX_60h9sXS0Q&minimal))

#### Use case: Direct links to related SERPs views

As a researcher, I want to access related resources from the SERP view by clicking on links/buttons, such as:

- the web archive snapshot (Memento URL),
- original SERP URL (either unmodified or with tracking parameters removed),
- (a search for) other SERPs with the same query (either from the same or different search providers),
- an [unfurl view of the SERP URL](https://dfir.blog/unfurl/?url=https://www.google.com/search?source=hp&ei=yTLGXeyKN_2y0PEP2smVuAg&q=dfir.blog&oq=dfir.blog&gs_l=psy-ab.3..0i30j0i8i30.1008.2701..2824...0.0..0.140.669.9j1....2..0....1..gws-wiz.....6..0i362i308i154i357j0j0i131j0i10j0i10i30j0i5i10i30j0i13j0i8i10i30.nDHWsi-Ws90&ved=0ahUKEwisk-WjmNzlAhV9GTQIHdpkBYcQ4dUDCAg&uact=5), and
- the SERP view in the "Pretend to be old Google" view;

so that I can navigate between SERPs views fast.

#### Use case: "Pretend to be old Google" view of SERP

As a researcher, I want to see how a specific archived SERP would have looked like if it were served by Google in 2002 so that I can analyze how SERPs have developed over time. This view would simulate the old Google SERP layout, but display the parsed query and results from the archived SERP.

This feature is optional and complex, so it is low-priority and would probably be implemented later.

The "pretend to be ..." view should be implemented in a way so that it can be extended to other points in time of the same search provider as well as to other search provider at different points in time. A better, more generic name may be in order.

#### Use case: Timeline of captures for same query and search provider

As a researcher, I want to see a timeline (e.g., a date histogram like [on the Wayback Machine](https://web.archive.org/web/20251104095020/https://www.google.com/web/20251104095020/https://www.google.com/), header toolbar) of captures for the same query and search provider, so that I can understand in which time periods and how often this query was captured.
From this timeline, I want to be able to click on other captures to view them.

#### Use case: View search provider metadata

As a researcher, I want to see the details of a specific search provider in the AQL, including its name, domains, URL patterns, so that I know the origin of a SERP.

#### Use case: View web archive metadata

As a researcher, I want to see the details of a specific web archive in the AQL, including its name, API URLs (CDX API and Memento API), and (optional) link to the archive's homepage, so that I know the provenance of an archived SERP.

#### Use case: Wikidata links and preview for search providers and web archives

As a researcher, when viewing the details of a specific search provider or web archive in the AQL browser, I want to see a link to its corresponding Wikidata entry (if available), so that I can obtain further information about them. I would also like to see a brief preview of key information from Wikidata directly in the AQL browser (e.g., founding date, logo, country, owner).

#### Use case: Descriptive statistics for search providers and web archives

As a researcher, when viewing the details of a specific search provider or web archive in the AQL browser, I want to see some descriptive statistics about the data associated with them in the AQL, such as the number of archived SERPs and unique queries, so that I can understand the amount of SERPs archived from a provider or archive. This could also include a histogram showing the number of archived SERPs over time or the date range in which SERPs were archived.

#### Use case: Deep-linking to specific views

As a researcher, I want to be able to deep-link to any of the above, and other views in the AQL browser (e.g., a specific SERP, search provider, web archive, or search for SERPs) via unique URLs, so that I can easily share these links with others or bookmark them for later reference.

As the maintainer of the AQL browser, I want to ensure that these URLs are stable over time and can be linked to in other resources (e.g., from a knowledge graph and/or ontology), so that there won't be dead links from outside sources.

Suggested URL structure:

- `/serps`: List of SERPs with search and filter options.
- `/serps/{serp_id}`: Detailed view of a specific SERP.
- `/serps/compare/{serp_id},{other_serp_ids...}`: Comparison view of two (or more?) SERPs.
- `/providers`: List of search providers.
- `/providers/{provider_id}`: Details about a specific search provider.
- `/archives`: List of web archives.
- `/archives/{archive_id}`: Details about a specific web archive.
- Further URLs as needed

### Epic: SERP search and browsing

This epic covers the functionality to search and browse archived SERPs in the AQL browser.

#### Use case: Basic search for SERPs

As a researcher, I want to search for archived SERPs by its query text so that I can access SERPs that matching the query, or SERPs that are relevant to the query.

A view that shows the search results shows, for instance, a ranking of queries in the AQL by their relevance to the researcher's search request, where each retrieved query shows the timeline view of SERPs that have been archived for that query.

#### Use case: SERP search "preview" with summary statistics

As a researcher, while entering my search query for SERPs, I want to first see a preview of matching queries with summary statistics (e.g., number of matching SERPs, date histogram, predominant search providers and web archives) before submitting the query, so that I can refine my query. After hitting enter, I would view the actual SERPs. This feature could look like a search bar pop-down as on Google, where search suggestions are made.

#### Use case: SERP search suggestions

As a researcher, I want to see suggestions for common queries (i.e., popular in the AQL) as I type my search query in the SERP search.

#### Use case: SERP Search filters

As a researcher, I want to filter archived SERPs by various criteria (e.g., date range of archival, search provider, web archive) so that I can narrow down my search results.
(This should look similar to filtering products by brand or price in an e-commerce store.)

#### Use case: "Fuzzy" SERP search mode

As a researcher, I want the search to match a broader set of SERPs, including those with similar queries or common misspellings, so that my typing mistakes are no problem. (Keywords: query expansion, spelling correction)

#### Use case: Advanced SERP search mode

As a researcher, I want to be able to use advanced search operators (e.g., boolean operators like AND or OR, phrase search, and basic wildcard operators at character level) to refine my SERP search in a "advanced search mode" so that I can narrow down search results very precisely.

#### Use case: SERP search sorting

As a researcher, I want to change the sorting of SERP search results (e.g., by date of archival, relevance to query) so that I can better find the SERPs I am looking for.

#### Use case: Overview of SERPs found in search

As a researcher, I want to see some overview statistics of the SERPs found in my search (e.g., exact number of matches, approximate number of unique queries, distribution over time (histogram like [on DBLP](https://dblp.org/search?q=test); right sidebar), predominant search providers and web archives) so that I can better understand the search results.

#### Use case: Pagination for SERP search

As a researcher, I want to navigate through the found SERPs in my search using pagination, while being able to select the number of search results, so that I can decide how many search results to look at with reasonable limits (e.g., 10, 100, 1000).

### Epic: Logging and analytics

This epic covers the functionality to log user interactions with the AQL browser for analytics purposes, i.e., to learn how researchers use the AQL data.

#### Use case: User identification

As the maintainer of the AQL browser, I want to uniquely identify users (e.g., via hashed IP addresses, or prefixes of IP addresses) so that I can analyze usage patterns while respecting user privacy.

#### Use case: User interaction logging

As the maintainer of the AQL browser, I want to log user interactions (e.g., searches performed, SERPs viewed) so that I can analyze usage patterns and improve the tool.
To not implement an own logging solution from scratch, rather use an existing logging tool like [bigbro](https://github.com/hscells/bigbro).

<!-- MARKER: Added the backlock to the SWEP project up to this point. -->

### Epic: Exports and filtering

#### Use case: Export SERP as run file

As an information retrieval researcher, I want to export the results of a specific archived SERP in a standard run file format (i.e., the [TREC run format](https://github.com/joaopalotti/trectools?tab=readme-ov-file#file-formats)) so that I can use it in my experiments.
This format depends on query and document IDs, so one first idea to derive a document ID could be to use the result block's UUID and for the query ID, a hash or encoding of the query text.

#### Use case: Export SERP search as run file

As an information retrieval researcher, when searching for archived SERPs, I want to export the top k matching SERPs and their results in a standard run file format (i.e., the [TREC run format](https://github.com/joaopalotti/trectools?tab=readme-ov-file#file-formats)) so that I can them in my experiments. Here, the k should be configurable but with reasonable limits (e.g., 10, 100, 1000).

#### Use case: Export SERP search as list of Memento URLs

As a researcher, when searching for archived SERPs, I want to export the list of the Memento URLs of the top k matching SERPs so that I can share them with outsiders. Here, the k should be configurable but not too large (e.g., 10, 100, 1000, 10k), to avoid privacy issues.
Another idea could be to rate-limit the exports based on their size (e.g., larger exports would be allowed only once per day) or to send export requests via email for very large exports (k > 1000?).

#### Use case: Server-side filtering

As the maintainer of the AQL browser, I want to be able to filter certain search providers, web archives, SERPs, or results from appearing in the AQL browser based on a server-side flag, so that we can meet compliance criteria.
The filtered-out data should still be present in the underlying AQL database, but not shown in the AQL browser nor in exports (unless a privileged user is trying to access them).

#### Use case: IR test collection builder

As an information retrieval researcher, I want to be able to build custom test collections from archived SERPs in the AQL browser by selecting specific SERPs, searches for SERPs, and their results, and exporting them.
The selection should be stored locally (e.g., in the browser's local storage) and only the final export request should be sent to the server.
I also want to be able to assign custom topic IDs to each selected SERP or SERP search for better organization.
This feature could look similar to building a shopping cart in an e-commerce store.

### Epic: Comparisons and statistics

#### Use case: Compare two SERPs

As a researcher, I want to compare two archived SERPs side-by-side to analyze differences in search results for the same query over time or between different search providers.
This comparison could look similar to [DiffIR](https://github.com/capreolus-ir/diffir) or directly re-use that library.

#### Use case: Compare two searches for SERPs

As a researcher, I want to compare the results of two different searches for archived SERPs (e.g., different filters applied) to analyze differences in the found SERPs.
This comparison could include a preview of differences in summary statistics (e.g., in the histogram).
This feature is optional and could be implemented later.

#### Use case: Descriptive statistics dashboard

As a researcher, I want to see a dashboard with descriptive statistics about the entire AQL dataset, such as:

- The number of archived SERPs over time
- Distribution of search providers and web archives (histogram over time)
- Most common queries over time
- (Optional) popular n-grams in queries over time
- Timelines of SERPs about major events (e.g., elections, pandemics) or periodic events (e.g., Christmas, Halloween, Black Friday; like in the ECIR paper under review)

This feature would look similar to [Google's Year in Search](https://trends.withgoogle.com/year-in-search/) (formerly Google Zeitgeist) and could be called "AQL Zeitgeist".

### Epic: User Management (not for SWEP)

#### Use case: User registration

As a maintainer, I want to be able to restrict access to certain views and functionalities of the AQL browser to registered users so that I have control over who can access, search, or export data.

There is no need to reimplement user management from scratch; rather use the [Disraptor](https://www.disraptor.org/) tool for that. Disraptor acts as a proxy and adds a Discourse-wrapper around a web pages served by an external backend server. This way, Disraptor helps to modularize user management from business logic. A good example of its usage is [TIRA](https://tira.io)

#### Use case: User roles

As a maintainer, I want to be able to assign user roles and access privileges for viewing, searching, and exporting the AQL so that I have control over who access what data.

When using Disraptor, the tool transmits user name and user roles to the backend server of the AQL browser, so that one can decide with each access whether a user has the correct privileges to access a resource.
