# **Auditing the Invisible Web: Deterministic Signals for AI Discoverability and RAG Optimization**

## **Executive Summary**

The transition from visual, browser-based web indexing to agentic, Retrieval-Augmented Generation (RAG) pipelines necessitates a fundamental shift in how digital information is audited. Conventional search engine optimization relies heavily on heuristics tailored to human presentation, such as metadata, heading hierarchies, readability scores, and keyword distributions. However, large language models, autonomous agents, and hybrid search infrastructures interact with the web through entirely different mathematical, topological, and structural mechanisms. This report introduces an exhaustive, ranked innovation backlog of novel, unconventional, and deterministic audit capabilities designed to detect friction points specific to artificial intelligence systems.  
By adapting principles from algorithmic information theory, network topology, compiler static analysis, and deep learning failure mode research, the evaluation identifies deterministic signals that directly impact context-window survivability, reciprocal rank fusion consensus, and community detection in knowledge graphs. For example, when an autonomous system attempts to resolve localized queries regarding emerging technology hubs or supply chain logistics in regions such as Ahmamau, Uttar Pradesh, India, standard metadata is insufficient. The AI relies on mathematically dense internal linking, unambiguous coreference resolution, and strict adherence to content negotiation protocols to synthesize accurate insights. The capabilities proposed herein operate strictly via deterministic local analysis, requiring no outsourced intelligence, third-party scoring interfaces, or browser automation. The result is a robust technical research and development roadmap for identifying vulnerabilities in how web data is discovered, retrieved, grounded, and synthesized by modern generative architecture.

## **Theoretical Frameworks and Innovation Vectors**

The capabilities proposed in this report are grounded in specialized domains adjacent to standard information retrieval. Understanding these theoretical underpinnings is necessary for implementing the deterministic heuristics outlined in the innovation backlog. The analysis moves beyond treating text as a bag of words and instead evaluates the web through the lens of algorithmic distance, topological density, and attention mechanics.

### **Algorithmic Information Theory and Kolmogorov Complexity**

Dense retrieval models map text into high-dimensional vector spaces. When web content contains high semantic redundancy—such as localized legal disclaimers, recurring procedural templates, or repetitive navigational text that evades simple HTML tag stripping—it dilutes the localized information density of the generated embeddings. This dilution severely degrades dot-product similarity scoring during the retrieval phase. Because true Kolmogorov complexity is mathematically non-computable, algorithmic information theory utilizes standard data compression algorithms, such as Lempel-Ziv or the zlib library, to approximate the ultimate compressed size of an object1.  
The Normalized Compression Distance (NCD) provides a parameter-free, universal similarity metric that computes the informational distance between two strings without requiring a neural network or external embedding API4. By utilizing the formula for NCD, auditors can calculate the precise algorithmic similarity between discrete HTML chunks7. Adapting NCD allows for the deterministic detection of semantic redundancy and template leakage that vector databases struggle to resolve, providing a mathematical proof of redundancy without needing to invoke an expensive language model8.

### **Large Language Model Attention Degradation and the U-Curve**

Transformer-based language models exhibit a documented vulnerability known as the "Lost in the Middle" phenomenon11. When processing long input contexts, attention mechanisms assign disproportionate weight to tokens at the beginning (primacy bias) and the end (recency bias) of the sequence11. Factual claims, numerical statistics, or precise entity definitions buried in the median span of an extracted text chunk suffer a drastic reduction in retrieval and synthesis accuracy, often leading to hallucinated or truncated answers12.  
This positional degradation occurs because attention mass gets spread thinner across more tokens as sequence length grows, diluting the effective signal of middle tokens relative to tokens near clear boundaries that serve as natural anchors16. Measuring the absolute token-depth positioning of critical entities allows auditors to predict context-window survivability without executing a language model inference pass. An audit tool can simply tokenize a page, locate the factual assertions, and map their geometric position against the known U-shaped performance curve of contemporary language models13.

### **Graph Topology and Agentic Sensemaking**

Modern agentic systems increasingly utilize graph-based retrieval-augmented generation architectures to achieve global sensemaking over large corpora19. These systems extract entities and relationships to form knowledge graphs, subsequently applying hierarchical community detection algorithms to generate clustered summaries. While earlier implementations relied on stochastic modularity optimization algorithms like Leiden clustering, current research demonstrates that ![][image1]\-core decomposition provides a deterministic, density-aware hierarchy particularly suited for sparse knowledge graphs20.  
The ![][image1]\-core decomposition organizes a network into nested layers of increasing minimum degree, creating a deterministic hierarchy that captures progressively denser and more cohesive substructures21. Analyzing a website's internal entity and link topology through a local ![][image1]\-core algorithm reveals whether the site's structural graph is mathematically capable of supporting coherent agentic community detection22. If a site mapping local business nodes in Ahmamau, Uttar Pradesh, India lacks sufficient interconnected edges to form a dense ![][image1]\-core community, the global map-reduce summarization step will inevitably fail to extract meaningful regional intelligence.

### **Hybrid Retrieval and Reciprocal Rank Fusion**

To combat the respective weaknesses of dense embeddings, which frequently fail at exact keyword or identifier matching, and sparse retrieval, which fails at semantic variance, production systems utilize hybrid search architectures23. The outputs from these parallel retrieval streams are merged using Reciprocal Rank Fusion, an algorithm formally introduced at SIGIR 2009 that aggregates rankings without requiring score normalization25. The standard formula allocates a score to each document based on the summation of its reciprocal rank positions, heavily favoring consensus between sparse and dense models28.  
However, this reliance on consensus creates a strict mathematical dependency on the underlying sparse index, typically an implementation of Okapi BM25. The BM25 algorithm utilizes a length normalization parameter that aggressively penalizes term frequency in excessively long documents31. Web pages with extreme structural length or a severe imbalance between alphanumeric identifiers and natural language will trigger a sparse retrieval failure. When the sparse model drops the document, the reciprocal rank fusion consensus is broken, causing the document to plummet in the final ranking sent to the generative model26.

### **Coreferential Ambiguity at Extraction Boundaries**

A pervasive cause of retrieval failure stems from the naive chunking strategies employed by data ingestion pipelines. When parsing HTML documents, systems typically fracture the text along DOM boundaries or fixed token limits. This process frequently severs syntactic dependencies, particularly anaphoric expressions where pronouns refer back to an entity established in a preceding chunk34.  
Recent research demonstrates that coreferential complexity severely hinders a retrieval model's ability to effectively interpret and represent documents17. If a text chunk begins with a demonstrative pronoun, the isolated vector embedding loses its semantic grounding38. Upon retrieval, the dense index will misalign the query, and the generative model will fail to synthesize the answer due to the missing antecedent. Resolving these dependencies through local static analysis allows an auditor to flag structural elements that are hostile to the chunking algorithms utilized by embedding pipelines.

## **Tier A: Hackathon Differentiators**

The following capabilities represent the highest-value innovations derived from the theoretical frameworks. They are highly novel, technically defensible, computationally lightweight, and explicitly designed to be executed without browser automation or external intelligence APIs.

### **Capability 1: Algorithmic Semantic Redundancy via NCD (NCD-01)**

The conventional approach to duplicate content relies on exact string matching or simple cryptographic hashing, which fails when text is heavily paraphrased or obfuscated by dynamic templating. This capability utilizes information theory to mathematically prove when structurally distinct elements offer zero novel information to an agentic fetcher.

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Algorithmic Semantic Redundancy via NCD (NCD-01) |
| **What it detects** | Severe informational redundancy across structurally distinct text chunks that use varying lexicons, indicating paraphrased boilerplate that exact-match deduplication algorithms miss. |
| **Why it matters specifically for AI systems** | Semantic redundancy creates dense, identical clusters in a vector database. When a hybrid system executes a similarity search, paraphrased redundant blocks monopolize the Top-K returned results, starving the language model's context window of the diverse information necessary for accurate synthesis7. |
| **Why it is novel** | It replaces computationally heavy local embedding models with a purely algorithmic, compression-based approximation of Kolmogorov complexity6. It provides a mathematical proof of redundancy without utilizing a neural network or executing semantic similarity matching. |
| **Detection methodology** | 1\. Extract raw text from sibling nodes in the DOM tree. 2\. Compress Chunk A (![][image2]) and Chunk B (![][image3]) using the standard zlib library. 3\. Concatenate the raw strings and compress the result (![][image4]). 4\. Calculate the Normalized Compression Distance: ![][image5]. 5\. Flag structural pairs where ![][image6], indicating they contain nearly identical algorithmic information despite differing word choices. |
| **Required inputs** | Raw text arrays extracted from distinct HTML block elements. |
| **Implementation feasibility** | Very High. Native zlib compression libraries exist in standard Python and Node environments, requiring no external dependencies. |
| **Evidence produced** | An ![][image7] quantitative distance matrix or ASCII heatmap of NCD scores proving that structurally separate sections of the site offer highly repetitive algorithmic information. |
| **False-positive risks** | Extremely short strings naturally compress poorly and yield unstable ratios, creating artificially high NCD scores. A minimum byte-length threshold is required to ensure statistical validity. |
| **Complexity** | Low. |
| **Innovation score** | 10 / 10 |
| **Evidence strength** | 10 / 10\. Firmly established in algorithmic information theory and proven highly effective for document clustering without semantic models in peer-reviewed IEEE literature2. |
| **Existing-capability overlap** | Avoids overlap with REN-07 (Boilerplate separation), which focuses on the structural extraction of body text versus navigation chrome, and ENT-04 (Canonicalisation), which targets exact lexical matches. |

### **Capability 2: Middle-Context Fact Interment (POS-01)**

The absolute geometric position of information within an HTML document is rarely considered outside the context of human visual layout. For an artificial intelligence, token depth is a critical predictor of factual recall and synthesis accuracy.

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Middle-Context Fact Interment (POS-01) |
| **What it detects** | High-value, isolated factual claims, numerical statistics, or precise named entities that are exclusively positioned in the median token-depth of a document without repetition at the margins. |
| **Why it matters specifically for AI systems** | Language models suffer from severe attention degradation for information located in the middle of long contexts11. A document optimized perfectly for dense retrieval will still trigger hallucinations during the generative phase if the extracted chunk forces the model to reason over mid-context tokens13. |
| **Why it is novel** | Conventional audits assess keyword frequency, semantic relevance, or heading structures. This metric evaluates the absolute mathematical token-depth geometry of entities, treating the document as an attention-weight surface rather than a bag of words. |
| **Detection methodology** | 1\. Extract raw text from the main HTML article body. 2\. Tokenize the text sequence into an array of length ![][image8]. 3\. Use static regex rules and local dependency parsing to extract target features such as numerical statistics or capitalized named entities. 4\. Calculate the relative position ![][image9] for each unique feature. 5\. Flag the document if ![][image10] of unique target facts fall strictly within the middle dead zone of ![][image11]. |
| **Required inputs** | Raw text parsed from the HTML document. |
| **Implementation feasibility** | High. Executable entirely in Python or Node using standard regular expressions and basic mathematical arrays. |
| **Evidence produced** | A programmatic token-depth distribution chart visually demonstrating the "dead zone" concentration of the page's factual claims, proving a high risk of attention failure. |
| **False-positive risks** | Highly linear narrative texts, such as historical chronologies, naturally distribute facts evenly across the document span. This triggers the threshold without the author necessarily intending to bury information. |
| **Complexity** | Low. |
| **Innovation score** | 9.5 / 10 |
| **Evidence strength** | 10 / 10\. Directly backed by extensive empirical research on language model context utilization, detailing the specific U-shaped performance curve11. |
| **Existing-capability overlap** | Completely distinct from RET-06 (Chunk quality), which evaluates the atomic nature of discrete paragraphs. POS-01 evaluates the holistic document span and its interaction with transformer attention mechanisms prior to arbitrary chunking. |

### **Capability 3: GraphRAG K-Core Density Deficit (KCORE-01)**

Global sensemaking requires documents to be interconnected in a manner that facilitates graph clustering. Evaluating a site's topological density reveals whether an agent can mathematically extract coherent communities of information.

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | GraphRAG K-Core Density Deficit (KCORE-01) |
| **What it detects** | A shallow internal entity-and-link topology that lacks mathematically cohesive subgraphs, preventing the extraction of hierarchical community summaries. |
| **Why it matters specifically for AI systems** | Advanced agentic systems use GraphRAG for corpus sensemaking19. If a website's cross-linking structure forms a sparse, shallow tree rather than a dense network, ![][image1]\-core decomposition fails to find communities, causing the agent's map-reduce summarization step to fail or return highly fragmented, low-quality context20. |
| **Why it is novel** | Adapts network science concepts to evaluate website link structures specifically for knowledge-graph community derivation, rather than utilizing traditional PageRank calculations or generic link-equity SEO audits. |
| **Detection methodology** | 1\. Parse a localized subset of the website's internal URLs (nodes) and hyperlinks (edges) using a bounded static HTTP fetcher. 2\. Load the graph topology into a local mathematical library such as networkx in Python. 3\. Execute a deterministic ![][image1]\-core decomposition algorithm to peel the graph into nested layers based on nodal degree. 4\. Flag architectures where the maximum core number is strictly ![][image12], indicating an inability to support robust community detection for agentic ingestion. |
| **Required inputs** | A localized edge list of internal hyperlinks generated from a small sample of parsed HTML pages. |
| **Implementation feasibility** | Medium. Requires a lightweight, bounded multi-page fetcher and a graph computation library, but entirely feasible within a static Python environment. |
| **Evidence produced** | A programmatic graph readout showing the maximum ![][image1]\-core depth, providing mathematical proof that the site lacks the interconnected contextual density required for GraphRAG pipelines. |
| **False-positive risks** | Small brochure websites or single-page applications inherently lack topological depth. This metric is most accurately applied to knowledge bases, documentation hubs, and extensive article repositories. |
| **Complexity** | Medium. |
| **Innovation score** | 9.5 / 10 |
| **Evidence strength** | 10 / 10\. Supported by recent computer science research detailing ![][image1]\-core hierarchies as a superior, deterministic alternative to stochastic Leiden clustering for scalable GraphRAG22. |
| **Existing-capability overlap** | None. Distinct from CIT-08 (Hub/authority link-graph), which evaluates external trust routing and inbound links. KCORE-01 strictly evaluates internal graph density for agentic community extraction. |

### **Capability 4: Anaphoric Ambiguity at Chunk Boundaries (COREF-01)**

The rigid nature of vector database ingestion pipelines creates severe vulnerabilities at the borders of text chunks, where syntactic context is easily destroyed.

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Anaphoric Ambiguity at Chunk Boundaries (COREF-01) |
| **What it detects** | Structural HTML elements whose opening sentences rely heavily on unresolved anaphora, specifically demonstrative or personal pronouns. |
| **Why it matters specifically for AI systems** | Retrieval-augmented generation pipelines aggressively fracture text at HTML boundaries. If a chunk begins with a pronoun whose antecedent was located in the preceding block, the isolated vector embedding loses its semantic grounding37. Upon retrieval, the dense index fails to align the query, and the language model hallucinates the missing antecedent39. |
| **Why it is novel** | Scopes specifically to the exact cut-points of standard AI chunkers by bridging structural DOM analysis with deterministic syntactic dependency parsing. |
| **Detection methodology** | 1\. Parse the DOM tree into atomic block elements (e.g., \<p\>, \<li\>, \<section\>). 2\. Extract the first sentence of every isolated block. 3\. Apply deterministic regex matching or lightweight part-of-speech tagging using a local spaCy instance to detect leading demonstrative pronouns (e.g., "This approach", "It is", "They are"). 4\. Calculate the "Coreferential Ambiguity Ratio" (ambiguous blocks / total blocks). Flag if the ratio exceeds ![][image13]. |
| **Required inputs** | The structural HTML DOM tree and its rendered text nodes. |
| **Implementation feasibility** | High. Can be built efficiently using standard string manipulation, regex libraries, or static NLP tokenizers. |
| **Evidence produced** | A targeted list of isolated sentences extracted from the site that visibly lack context when read alone, proving that the website's structure is actively hostile to semantic chunking algorithms. |
| **False-positive risks** | Conversational copywriting styles naturally utilize a higher density of pronouns for flow. However, this remains an objective hazard for retrieval pipelines regardless of the author's stylistic intent. |
| **Complexity** | Low. |
| **Innovation score** | 9 / 10 |
| **Evidence strength** | 9 / 10\. Documented extensively in natural language processing research, which identifies coreferential complexity as a primary disruptor of in-context learning and retrieval relevance17. |
| **Existing-capability overlap** | Avoids CQ-01 (Answer extractability) by utilizing a strictly deterministic syntactic trigger rather than relying on abstract, generalized readability scores. |

### **Capability 5: Agentic Content Negotiation Entropy (ACN-01)**

Agentic crawlers actively attempt to minimize their bandwidth footprint and token consumption through HTTP protocol negotiation. Servers that ignore these protocols force agents into expensive extraction pathways.

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Agentic Content Negotiation Entropy (ACN-01) |
| **What it detects** | Origin servers that fail to honor proactive HTTP content negotiation when an automated crawler explicitly requests lightweight data formats over heavy HTML. |
| **Why it matters specifically for AI systems** | Modern crawlers routinely utilize Accept: text/markdown or Accept: application/json headers to bypass heavy DOM parsing, effectively saving up to 80% on language model token counts43. Servers that ignore these headers force agents to ingest heavy, token-expensive HTML, increasing latency and operational costs45. |
| **Why it is novel** | Tests the underlying HTTP protocol's negotiation layer rather than analyzing the rendered site payload or searching for alternate hardcoded URLs. |
| **Detection methodology** | 1\. Issue an HTTP GET request to the target URL with the explicit header Accept: text/markdown, application/json;q=0.9, text/html;q=0.1. 2\. Evaluate the response's Content-Type header. 3\. Flag if the server defaults to returning text/html, proving it lacks machine-readable negotiation capabilities and ignores quality weighting. |
| **Required inputs** | HTTP response headers from a targeted requests or fetch call. |
| **Implementation feasibility** | Very High. Extremely simple to implement via standard HTTP libraries without requiring any complex parsing. |
| **Evidence produced** | A raw HTTP request/response log demonstrating the agent's explicit Accept preference being actively ignored by the origin server. |
| **False-positive risks** | Certain highly secure Web Application Firewalls strip incoming Accept headers to prevent browser fingerprinting, which will present externally as a failure of the origin server's negotiation capability. |
| **Complexity** | Low. |
| **Innovation score** | 8.5 / 10 |
| **Evidence strength** | 10 / 10\. Based directly on RFC 9110 standard specifications for proactive content negotiation between HTTP clients and servers45. |
| **Existing-capability overlap** | Completely distinct from PER-07 (Markdown content negotiation), which explicitly checks for the availability of alternative .md file variants. ACN-01 checks the dynamic HTTP protocol handling on the primary canonical URL. |

### **Capability 6: Hybrid Search Length Normalization Trap (BM25-01)**

The mathematical mechanics of sparse retrieval dictate that document length is an active liability for exact-match ranking, creating a hidden trap for comprehensive articles.

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Hybrid Search Length Normalization Trap (BM25-01) |
| **What it detects** | Excessively long documents lacking hard semantic breaks that suffer catastrophic mathematical penalties from sparse retrieval length normalization parameters. |
| **Why it matters specifically for AI systems** | Reciprocal Rank Fusion algorithms rely heavily on the sparse retrieval component (BM25) to lock onto exact identifiers23. BM25 uses a standard parameter (![][image14]) that aggressively penalizes term frequency in excessively long documents31. A monolithic document will drop out of the sparse ranking entirely, breaking the rank fusion consensus and disappearing from the agent's context26. |
| **Why it is novel** | It predicts the mathematical failure of a specific, ubiquitous vector-database ranking algorithm using deterministic statistical modeling, rather than evaluating generalized keyword density. |
| **Detection methodology** | 1\. Calculate the raw token or word length of the target document (![][image15]). 2\. Assume a standard corpus average document length (![][image16] words). 3\. Execute the BM25 denominator penalty calculation: ![][image17]. 4\. Flag the document if the length penalty reduces the theoretical sparse keyword score by ![][image10], indicating imminent rank fusion failure. |
| **Required inputs** | Accurate word or token counts of the extracted HTML document text. |
| **Implementation feasibility** | High. Requires only basic string tokenization and a simple algebraic computation. |
| **Evidence produced** | A mathematical simulation chart displaying the severe percentage drop in retrieval score relative to an optimally chunked document, proving the document's vulnerability to length penalties. |
| **False-positive risks** | The exact average document length (![][image18]) of the indexing system's proprietary corpus is inherently unknown, requiring heuristic assumptions that may differ slightly from the production index. |
| **Complexity** | Low. |
| **Innovation score** | 9 / 10 |
| **Evidence strength** | 10 / 10\. Solidly supported by foundational information retrieval literature on BM25 scaling behaviors and reciprocal rank fusion optimization25. |
| **Existing-capability overlap** | None. Distinct from CQ-04 (Granularity mismatch), which evaluates the semantic scope of answers. BM25-01 evaluates pure mathematical length penalties regardless of semantic quality. |

### **Capability 7: Self-Reflective API Validation Exposure (SRA-01)**

When autonomous agents interface directly with website endpoints, traditional human-readable error messages become operational roadblocks that drain compute budgets.

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Self-Reflective API Validation Exposure (SRA-01) |
| **What it detects** | Exposed API endpoints that return unstructured, human-readable prose for validation errors instead of structured, machine-readable recovery schemas. |
| **Why it matters specifically for AI systems** | Autonomous agents increasingly use tool-calling to interface with APIs. When an error occurs, language models struggle to infer the correct parameter change from verbose text, leading to infinite retry loops and rapid context exhaustion49. Self-reflective APIs return a structured suggestions payload, allowing the agent to deterministically repair the request without invoking complex reasoning50. |
| **Why it is novel** | Shifts the focus from traditional REST compliance to agent-specific error-handling logic explicitly designed for autonomous recovery pathways. |
| **Detection methodology** | 1\. Retrieve the website's OpenAPI specification (e.g., via llms.txt or a .well-known directory). 2\. Parse the JSON/YAML schema for 400-level HTTP error responses. 3\. Flag if the error schema lacks arrays or structured objects for automated feedback, such as missing RFC 7807 problem details or explicit suggestions fields. |
| **Required inputs** | The target website's OpenAPI JSON or YAML specification files. |
| **Implementation feasibility** | Medium. Requires the target site to expose a publicly accessible OpenAPI specification, followed by standard JSON parsing. |
| **Evidence produced** | A precise printout of the API's failure schema proving that it expects human developer intervention rather than facilitating autonomous agent recovery. |
| **False-positive risks** | Certain APIs may output highly deterministic, single-string error codes that advanced language models can successfully parse despite the lack of formal JSON arrays. |
| **Complexity** | Medium. |
| **Innovation score** | 9.5 / 10 |
| **Evidence strength** | 10 / 10\. Based directly on peer-reviewed 2026 research identifying that structural schema beats plain-English verbosity in agent API recovery tasks49. |
| **Existing-capability overlap** | None. INF-05 details normalized finding contracts for the audit tool itself, whereas SRA-01 evaluates the structure of the target website's API endpoints. |

## **Tier B: Interesting Extensions**

The capabilities in Tier B offer highly unconventional approaches to discoverability auditing. While slightly more complex to implement or targeting secondary failure modes, they provide powerful insights into how web infrastructure interacts with AI fetchers.

### **Capability 8: W3C PROV-O Lineage Machine-Readability (PROV-01)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | W3C PROV-O Lineage Machine-Readability (PROV-01) |
| **What it detects** | The absolute absence of semantic provenance graphs tracking the origin, lineage, and generation mechanics of the data presented on the page. |
| **Why it matters specifically for AI systems** | Trust and citability in generative systems rely heavily on grounding outputs in verifiable sources. Utilizing the W3C PROV-O ontology allows agents to semantically verify data trails, drastically reducing hallucination risks when aggregating statistics52. |
| **Why it is novel** | Evaluates specialized semantic Web 3.0 ontologies focused strictly on provenance tracking, rather than generic Schema.org entity definitions. |
| **Detection methodology** | 1\. Parse the document's \<head\> and body for JSON-LD or RDFa tags. 2\. Execute string matching for the namespace declaration http://www.w3.org/ns/prov\#. 3\. Flag the absence of explicit lineage mapping entities (e.g., prov:Entity, prov:Activity, prov:wasGeneratedBy). |
| **Required inputs** | JSON-LD or RDFa data blocks extracted from the raw HTML. |
| **Implementation feasibility** | High. Straightforward JSON and DOM parsing. |
| **Evidence produced** | A clear indication of a missing provenance graph, accompanied by a structural example of the exact verification data the AI agent currently lacks. |
| **False-positive risks** | W3C PROV-O remains a highly specialized implementation. Almost all sites will flag this, making it a forward-looking, aspirational audit metric rather than a baseline expectation. |
| **Complexity** | Low. |
| **Innovation score** | 8 / 10 |
| **Evidence strength** | 9 / 10\. Validated by W3C standards and biomedical semantic parsing literature utilizing PROV-O for simulation traceability54. |
| **Existing-capability overlap** | Avoids overlap with ENT-01 (Schema.org presence), as PROV-01 isolates the highly specialized capability of rigorous data lineage tracking necessary for fact-checking. |

### **Capability 9: Agentic Context-Budget Fetch Survivability (HRR-01)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Agentic Context-Budget Fetch Survivability (HRR-01) |
| **What it detects** | Servers that actively block or fail to support HTTP byte-range requests for large documents. |
| **Why it matters specifically for AI systems** | Multi-hop agents and context-budget-aware fetchers regularly attempt to partially fetch large datasets to evaluate metadata headers without blowing out their token limits. A lack of range-request support forces the agent to download monolithic payloads, leading to automatic termination by budget governors57. |
| **Why it is novel** | Focuses on a low-level HTTP transport feature explicitly manipulated by autonomous agents to preserve inference compute during dynamic discovery. |
| **Detection methodology** | 1\. Send an HTTP HEAD request to detect the Accept-Ranges: bytes header. 2\. Issue an HTTP GET request with the header Range: bytes=0-500. 3\. Validate that the server responds with a 206 Partial Content status. Flag if it responds with a 200 OK (transmitting the entire file) or a 4xx/5xx rejection. |
| **Required inputs** | Target URL HTTP request generation and header evaluation. |
| **Implementation feasibility** | High. Standard HTTP request manipulation utilizing native libraries. |
| **Evidence produced** | HTTP response logs demonstrating the server's failure to respect byte-range constraints, proving it is hostile to bandwidth-constrained crawlers. |
| **False-positive risks** | Certain CDN configurations aggressively strip range requests as a blunt security measure, obfuscating the origin server's true technical capabilities. |
| **Complexity** | Low. |
| **Innovation score** | 7.5 / 10 |
| **Evidence strength** | 8 / 10\. Extensively documented in crawler architecture literature regarding web cache efficiency and agent footprint reduction techniques59. |
| **Existing-capability overlap** | Excludes overlap with INF-02 (Fetch layer) by testing a highly specific byte-range protocol rather than generalized HTTP availability. |

### **Capability 10: Vector Invalidation ETag Friction (ETAG-01)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Vector Invalidation ETag Friction (ETAG-01) |
| **What it detects** | Missing, weak, or hyper-volatile HTTP ETag headers that mutate on every request without substantial changes to the core semantic payload. |
| **Why it matters specifically for AI systems** | Search engines maintain massive vector databases and rely on ETag headers to rapidly determine if a document requires expensive re-embedding. If an ETag is hyper-volatile due to dynamic ad injection or timestamping, the crawler wastes compute re-indexing unchanged semantics, or gives up, leading to stale vectors28. |
| **Why it is novel** | Correlates standard HTTP caching mechanisms directly to the massive computational cost of dense vector embedding updates. |
| **Detection methodology** | 1\. Fetch the target URL and record the ETag and a cryptographic hash of the extracted text payload. 2\. Introduce a delay (e.g., 30 seconds) and execute a second fetch. 3\. Flag if the semantic text payload hash is identical but the ETag has mutated, indicating cache-busting volatility that disrupts indexers. |
| **Required inputs** | Sequential HTTP Headers and raw text string hashing. |
| **Implementation feasibility** | High. Requires two asynchronous HTTP calls and basic string hashing. |
| **Evidence produced** | Log output proving that identical semantic text content generates diverging HTTP cache validation tokens, unnecessarily triggering re-indexing protocols. |
| **False-positive risks** | The server might utilize strong ETags that accurately reflect minor byte-level changes in the invisible DOM chrome that do not affect the visible text, acting as designed but still frustrating semantic indexers. |
| **Complexity** | Low. |
| **Innovation score** | 8 / 10 |
| **Evidence strength** | 8 / 10\. A well-known issue in crawler architecture adapted directly to the cost constraints and invalidation protocols of distributed vector databases. |
| **Existing-capability overlap** | None. Distinct from CQ-10 (Temporal freshness), which focuses on semantic text-level contradictions rather than infrastructure caching tokens. |

### **Capability 11: Hybrid Search Vocabulary Divergence (RRF-02)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Hybrid Search Vocabulary Divergence (RRF-02) |
| **What it detects** | Text chunks exhibiting an extreme statistical imbalance between alphanumeric identifiers and natural language semantic descriptors. |
| **Why it matters specifically for AI systems** | Documents succeeding in hybrid retrieval must satisfy both the sparse retriever and the dense retriever. If a chunk is purely alphanumeric SKUs without natural language context, the dense model fails to map it in the semantic vector space. The ensuing rank fusion drops the document from the final ranking due to lack of consensus24. |
| **Why it is novel** | Evaluates lexical composition specifically to uncover vulnerabilities in multi-vector and hybrid scoring architectures. |
| **Detection methodology** | 1\. Extract text chunks from the document. 2\. Execute regular expressions to identify highly specific non-dictionary strings (e.g., alphanumeric SKUs, hex codes, UUIDs). 3\. Calculate the ratio of these identifiers to standard dictionary tokens. 4\. Flag chunks exhibiting extreme skews (e.g., ![][image10] identifier density), marking them as invisible to semantic dense models. |
| **Required inputs** | Parsed and tokenized document text. |
| **Implementation feasibility** | High. Requires basic NLP tokenization and dictionary matching capabilities. |
| **Evidence produced** | A calculated divergence score alongside a list of isolated identifiers that mathematically lack the semantic grounding necessary for dense retrieval. |
| **False-positive risks** | Data tables, such as technical specification sheets, naturally exhibit extreme skews and are intentionally designed without prose, requiring targeted processing exceptions to prevent false flags. |
| **Complexity** | Low. |
| **Innovation score** | 8.5 / 10 |
| **Evidence strength** | 9 / 10\. Substantiated by information retrieval research detailing the failures of dense models against out-of-vocabulary technical identifiers in hybrid environments26. |
| **Existing-capability overlap** | Separated from RET-05 (Domain-specific terminology) by utilizing strict identifier-to-prose ratios mathematically designed to trigger fusion failure. |

### **Capability 12: HTTP Link-Header Relationship Orphanage (LNK-01)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | HTTP Link-Header Relationship Orphanage (LNK-01) |
| **What it detects** | The absence of RFC 8288 standard Link headers denoting alternate representations or API endpoints associated with the current resource. |
| **Why it matters specifically for AI systems** | Headless agents benefit immensely from discovering machine-readable API documentation or alternate JSON endpoints without executing expensive DOM parsing. If an agent must download and parse the full HTML to find a link to the corresponding API, it wastes processing cycles. Exposing this via the Link HTTP header allows immediate pivot and discovery61. |
| **Why it is novel** | Checks the HTTP transport layer for semantic routing signals defined in RFC 8288 and RFC 8631, completely bypassing the HTML body. |
| **Detection methodology** | 1\. Fetch the target URL's headers. 2\. Inspect the Link header for relations such as rel="alternate", rel="service-doc", or rel="service-desc" pointing to JSON or OpenAPI definitions. 3\. Flag if the resource contains an API counterpart in the DOM but fails to declare it in the HTTP headers. |
| **Required inputs** | HTTP Headers. |
| **Implementation feasibility** | Very High. Native HTTP library feature. |
| **Evidence produced** | Demonstration that the site forces AI agents to parse the HTML DOM to discover API links rather than exposing them cleanly in the transport headers. |
| **False-positive risks** | The site may genuinely not possess an alternate machine-readable representation, in which case the absence of the header is appropriate. |
| **Complexity** | Low. |
| **Innovation score** | 8 / 10 |
| **Evidence strength** | 10 / 10\. Based directly on IETF standards for Web Linking (RFC 8288\) and Web Service descriptions (RFC 8631\)63. |
| **Existing-capability overlap** | None. |

### **Capability 13: Internal PageRank Centrality Starvation (PR-01)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Internal PageRank Centrality Starvation (PR-01) |
| **What it detects** | Critical informational pages (e.g., technical specifications, legal policies, API docs) that are mathematically starved of internal link weight. |
| **Why it matters specifically for AI systems** | Agentic crawlers operate on strict depth and budget limits. They prioritize traversal based on graph centrality. If a critical page is buried deeply in the site hierarchy with few inbound internal links, it possesses a low local PageRank score and will be abandoned by the crawler before ingestion65. |
| **Why it is novel** | Uses directed graph analysis locally to simulate crawler prioritization, rather than relying on XML sitemaps or superficial click-depth metrics. |
| **Detection methodology** | 1\. Crawl a subset of the website's internal structure. 2\. Build a directed graph of internal links using networkx. 3\. Execute the local PageRank algorithm on the graph. 4\. Identify pages classified as "informational" via URL structure. Flag those falling in the bottom 10% of the PageRank distribution. |
| **Required inputs** | A localized internal link graph. |
| **Implementation feasibility** | Medium. Requires localized crawling and graph processing. |
| **Evidence produced** | A local PageRank score distribution showing that critical informational nodes are mathematically invisible to bounded agentic crawlers. |
| **False-positive risks** | Pages with low centrality might be appropriately deprecated or archived content that the webmaster intentionally wants to suppress. |
| **Complexity** | Medium. |
| **Innovation score** | 8.5 / 10 |
| **Evidence strength** | 10 / 10\. Foundational to graph theory and web crawler prioritization mechanisms68. |
| **Existing-capability overlap** | Distinct from EN-08 (On-site findability), which focuses on UI-level navigation elements for human visitors. |

### **Capability 14: OpenIE Triple Extraction Yield (OIE-01)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | OpenIE Triple Extraction Yield (OIE-01) |
| **What it detects** | Highly convoluted sentence structures that prevent the deterministic extraction of subject-predicate-object knowledge triples. |
| **Why it matters specifically for AI systems** | Automated knowledge graph constructors rely on Open Information Extraction (OpenIE) to populate entity relationships71. If sentences utilize excessive passive voice, nested clauses, or fragmented syntax, triple extraction fails, rendering the text useless for automated ontology generation. |
| **Why it is novel** | Evaluates text strictly on its mechanical compatibility with deterministic natural language processing parsers, bypassing subjective readability formulas. |
| **Detection methodology** | 1\. Parse text from the main content body. 2\. Utilize a local spaCy dependency parser to execute a rule-based extraction of (Subject, Predicate, Object) triples. 3\. Calculate the "Yield Ratio": the number of cleanly extracted triples divided by total sentences. 4\. Flag if the yield falls below a defined baseline, indicating AI-hostile syntax. |
| **Required inputs** | Rendered text and a local dependency parsing library. |
| **Implementation feasibility** | Medium. Requires the integration of a library like spaCy for static NLP processing. |
| **Evidence produced** | A report detailing the low volume of extractable knowledge triples, proving that the text cannot be effectively converted into structured knowledge graph data. |
| **False-positive risks** | Highly stylistic or literary texts will score poorly, though this accurately reflects their unsuitability for rigid automated knowledge extraction. |
| **Complexity** | Medium. |
| **Innovation score** | 8.5 / 10 |
| **Evidence strength** | 9 / 10\. Based on standard Open Information Extraction principles used in building automated knowledge bases71. |
| **Existing-capability overlap** | Avoids CQ-11 (Fluency/readability), utilizing a strict mechanistic measurement of NLP parseability rather than human-centric reading grade levels. |

### **Capability 15: Global Sensemaking Hierarchy Deficit (GSH-01)**

| Parameter | Specification |
| :---- | :---- |
| **Proposed capability** | Global Sensemaking Hierarchy Deficit (GSH-01) |
| **What it detects** | HTML documents lacking the rigorous, logical section nesting required to facilitate map-reduce summarization algorithms. |
| **Why it matters specifically for AI systems** | Generative models summarizing massive documents utilize a map-reduce methodology: mapping over local chunks to generate partial summaries, then reducing those into a global answer. If the document lacks explicitly nested semantic boundaries (e.g., sections properly bounded by \<h2\> containing distinct \<h3\> children), the mapping phase loses context, corrupting the final global synthesis73. |
| **Why it is novel** | Analyzes document structure specifically through the lens of map-reduce algorithmic requirements rather than simple accessibility standards. |
| **Detection methodology** | 1\. Parse the HTML heading structure into a DOM tree. 2\. Evaluate the containment geometry: does every lower-level heading physically reside within a clearly delineated parent semantic tag (e.g., \<article\> or \<section\>)? 3\. Flag if the tree is flat (e.g., 20 \<h2\> tags with no structural grouping), indicating a failure to support hierarchical map-reduce operations. |
| **Required inputs** | The structural HTML DOM tree. |
| **Implementation feasibility** | High. Simple DOM parsing and tree traversal. |
| **Evidence produced** | A visual printout of the corrupted or flattened hierarchy, demonstrating the lack of boundaries necessary for segmented summarization. |
| **False-positive risks** | Short documents naturally utilize flat hierarchies without incurring map-reduce penalties. |
| **Complexity** | Low. |
| **Innovation score** | 7.5 / 10 |
| **Evidence strength** | 8 / 10\. Backed by research identifying structural logic as a prerequisite for query-focused summarization over large corpora73. |
| **Existing-capability overlap** | Distinct from RET-08 (Heading hierarchy integrity). RET-08 checks for skipped levels (e.g., H1 to H3). GSH-01 checks for the physical DOM containment of sections required for automated chunk mapping. |

## **Final Ranking**

The proposed capabilities have been sorted to highlight their hackathon viability, novelty, and the technical strength of the mechanisms involved. The ranking prioritizes algorithms that are simple to implement, rely on deterministic local execution, and produce highly visual or mathematically profound evidence of AI discoverability friction.

| Rank | Capability | Novelty | AI Relevance | Implementability | Evidence Quality | Wow Factor |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **1** | Algorithmic Semantic Redundancy via NCD (NCD-01) | High | High | High | High | 10 |
| **2** | Middle-Context Fact Interment (POS-01) | High | High | High | High | 9.5 |
| **3** | GraphRAG K-Core Density Deficit (KCORE-01) | High | High | Medium | High | 9.5 |
| **4** | Self-Reflective API Validation Exposure (SRA-01) | High | Medium | Medium | High | 9.5 |
| **5** | Anaphoric Ambiguity at Chunk Boundaries (COREF-01) | High | High | High | Medium | 9 |
| **6** | Hybrid Search Length Normalization Trap (BM25-01) | High | High | High | High | 9 |
| **7** | Agentic Content Negotiation Entropy (ACN-01) | Medium | High | High | High | 8.5 |
| **8** | Internal PageRank Centrality Starvation (PR-01) | Medium | High | Medium | High | 8.5 |
| **9** | OpenIE Triple Extraction Yield (OIE-01) | Medium | High | Medium | Medium | 8.5 |
| **10** | Hybrid Search Vocabulary Divergence (RRF-02) | Medium | High | High | Medium | 8.5 |
| **11** | HTTP Link-Header Relationship Orphanage (LNK-01) | Medium | High | High | High | 8 |
| **12** | Vector Invalidation ETag Friction (ETAG-01) | Medium | High | High | Medium | 8 |
| **13** | W3C PROV-O Lineage Machine-Readability (PROV-01) | Medium | High | High | Medium | 8 |
| **14** | Global Sensemaking Hierarchy Deficit (GSH-01) | Medium | High | High | Medium | 7.5 |
| **15** | Agentic Context-Budget Fetch Survivability (HRR-01) | Medium | Medium | High | High | 7.5 |

## **Top 5 Recommendations for Hackathon Implementation**

The following five capabilities offer the optimal innovation-to-effort ratio, representing technically defensible, highly novel concepts that can be rapidly prototyped in a deterministic Python or Node environment without relying on browser automation or external intelligence scores.

### **1\. Algorithmic Semantic Redundancy via NCD (NCD-01)**

This capability possesses an exceptional "wow factor" because it performs highly sophisticated semantic analysis without utilizing an LLM, third-party API, or heavy embedding model. By simply utilizing the native zlib library to approximate Kolmogorov complexity, a hackathon team can instantly generate impressive ![][image7] heatmaps proving that a website is bloated with algorithmic redundancy. It demonstrates a deep understanding of vector database poisoning and information theory while remaining mathematically elegant, localized, and highly visual.

### **2\. Middle-Context Fact Interment (POS-01)**

Addressing the "Lost in the Middle" failure mode connects the audit directly to the most prominent architectural constraint of current large language models. This capability is exceptionally straightforward to implement using basic array mathematics and regex tokenization. The resulting output—a geometric token-depth distribution chart highlighting the attention "dead zone"—provides an immediate, visceral demonstration to judges of how a website is fundamentally misaligned with transformer attention mechanisms, bridging the gap between web development and deep learning constraints.

### **3\. GraphRAG K-Core Density Deficit (KCORE-01)**

While slightly more complex as it requires localized crawling, leveraging a library like networkx to run a ![][image1]\-core decomposition provides a stunning technical demonstration. It moves the conversation completely away from basic "link juice" heuristics and firmly into the realm of modern network science and knowledge graph topologies. Showing that a site mathematically lacks the internal density to support hierarchical community detection proves a profound comprehension of cutting-edge agentic workflows and sensemaking architectures.

### **4\. Self-Reflective API Validation Exposure (SRA-01)**

This capability shifts the audit from passive content consumption to active agentic tool use. It is highly implementable, requiring only the retrieval and parsing of an OpenAPI specification document. Demonstrating that an API forces an autonomous agent into a retry loop by providing verbose human text instead of a structured suggestions payload highlights a sophisticated understanding of how agents actually operate in the wild, offering a clear, programmatic standard for "AI-ready" endpoints.

### **5\. Anaphoric Ambiguity at Chunk Boundaries (COREF-01)**

This approach elegantly bridges the gap between structural DOM parsing and linguistic dependency. Implementing a lightweight script to identify structural HTML blocks that begin with unresolved demonstrative pronouns is highly feasible and computationally cheap. Presenting judges with a list of extracted, contextless sentences mathematically proves that standard ingestion pipelines will fail on the audited site, highlighting a nuanced understanding of retrieval operations and the physical mechanics of vector chunking.

#### **Works cited**

> 1. NCD: Music Genre Classification Method | PDF | Phylogenetic Tree, [https://www.scribd.com/document/48629439/project-synopsis-rahul](https://www.scribd.com/document/48629439/project-synopsis-rahul)  
> 2. Software Documents: Comparison and Measurement, [https://www.cas.mcmaster.ca/\~lawford/papers/seke07.pdf](https://www.cas.mcmaster.ca/~lawford/papers/seke07.pdf)  
> 3. Clustering by Compression \- arXiv, [https://arxiv.org/pdf/cs/0312044](https://arxiv.org/pdf/cs/0312044)  
> 4. Clustering by Compression \- UC Davis Mathematics, [https://www.math.ucdavis.edu/\~saito/data/acha.read.w17/cilibrasi-vitanyi\_clustering-by-compression.pdf](https://www.math.ucdavis.edu/~saito/data/acha.read.w17/cilibrasi-vitanyi_clustering-by-compression.pdf)  
> 5. \[cs/0312044\] Clustering by compression \- arXiv, [https://arxiv.org/abs/cs/0312044](https://arxiv.org/abs/cs/0312044)  
> 6. Normalized compression distance \- Wikipedia, [https://en.wikipedia.org/wiki/Normalized\_compression\_distance](https://en.wikipedia.org/wiki/Normalized_compression_distance)  
> 7. (PDF) Efficient Compression-Based Low-resource Text Classification, [https://www.researchgate.net/publication/398285366\_Efficient\_Compression-Based\_Low-resource\_Text\_Classification](https://www.researchgate.net/publication/398285366_Efficient_Compression-Based_Low-resource_Text_Classification)  
> 8. Clustering Fetal Heart Rate Tracings by Compression \- CWI, [https://homepages.cwi.nl/\~paulv/papers/cbms06.pdf](https://homepages.cwi.nl/~paulv/papers/cbms06.pdf)  
> 9. An Introduction to Kolmogorov Complexity and Its Applications, [https://www.researchgate.net/publication/345441271\_An\_Introduction\_to\_Kolmogorov\_Complexity\_and\_Its\_Applications](https://www.researchgate.net/publication/345441271_An_Introduction_to_Kolmogorov_Complexity_and_Its_Applications)  
> 10. (PDF) Compression-Based Similarity \- ResearchGate, [https://www.researchgate.net/publication/224264389\_Compression-Based\_Similarity](https://www.researchgate.net/publication/224264389_Compression-Based_Similarity)  
> 11. Lost in the Middle: How Language Models Use Long Contexts, [https://www.researchgate.net/publication/378284067\_Lost\_in\_the\_Middle\_How\_Language\_Models\_Use\_Long\_Contexts](https://www.researchgate.net/publication/378284067_Lost_in_the_Middle_How_Language_Models_Use_Long_Contexts)  
> 12. Lost in the Middle: How Language Models Use Long Contexts, [https://direct.mit.edu/tacl/article/doi/10.1162/tacl\_a\_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Middle-How-Language-Models-Use-Long)  
> 13. Lost in the Middle: How Language Models Use Long Contexts \- arXiv, [https://arxiv.org/html/2307.03172v1](https://arxiv.org/html/2307.03172v1)  
> 14. Lost in the Middle: How Language Models Use Long Contexts, [https://aclanthology.org/2024.tacl-1.9/](https://aclanthology.org/2024.tacl-1.9/)  
> 15. arXiv:2307.03172v3 \[cs.CL\] 20 Nov 2023, [https://arxiv.org/pdf/2307.03172](https://arxiv.org/pdf/2307.03172)  
> 16. The “Lost in the Middle” Problem in LLMs | by Rajveer Rathod, [https://medium.com/@rajveer.rathod1301/the-lost-in-the-middle-problem-in-llms-b0d88e13f025](https://medium.com/@rajveer.rathod1301/the-lost-in-the-middle-problem-in-llms-b0d88e13f025)  
> 17. The Transformative Effect of Coreference Resolution on Retrieval, [https://arxiv.org/html/2507.07847v3](https://arxiv.org/html/2507.07847v3)  
> 18. Nelson Liu \- Stanford Computer Science, [https://cs.stanford.edu/\~nfliu/](https://cs.stanford.edu/~nfliu/)  
> 19. A GraphRAG Approach to Query-Focused Summarization \- arXiv, [https://arxiv.org/html/2404.16130v2](https://arxiv.org/html/2404.16130v2)  
> 20. Core-based Hierarchies for Efficient GraphRAG \- arXiv, [https://arxiv.org/html/2603.05207v2](https://arxiv.org/html/2603.05207v2)  
> 21. Core-based Hierarchies for Efficient GraphRAG \- arXiv, [https://arxiv.org/pdf/2603.05207](https://arxiv.org/pdf/2603.05207)  
> 22. K-core based hierarchical community construction as an alternative, [https://github.com/microsoft/graphrag/issues/2407](https://github.com/microsoft/graphrag/issues/2407)  
> 23. Hybrid Search for RAG: BM25, SPLADE, and Vector Search Combined, [https://www.premai.io/blog/hybrid-search-for-rag-bm25-splade-and-vector-search-combined/](https://www.premai.io/blog/hybrid-search-for-rag-bm25-splade-and-vector-search-combined/)  
> 24. Hybrid Search in RAG: Dense \+ Sparse (BM25/SPLADE ... \- GoPenAI, [https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e](https://blog.gopenai.com/hybrid-search-in-rag-dense-sparse-bm25-splade-reciprocal-rank-fusion-and-when-to-use-which-fafe4fd6156e)  
> 25. \[PDF\] Reciprocal rank fusion outperforms condorcet and individual, [https://www.semanticscholar.org/paper/Reciprocal-rank-fusion-outperforms-condorcet-and-Cormack-Clarke/9e698010f9d8fa374e7f49f776af301dd200c548](https://www.semanticscholar.org/paper/Reciprocal-rank-fusion-outperforms-condorcet-and-Cormack-Clarke/9e698010f9d8fa374e7f49f776af301dd200c548)  
> 26. Advanced RAG — Understanding Reciprocal Rank Fusion in Hybrid, [https://glaforge.dev/posts/2026/02/10/advanced-rag-understanding-reciprocal-rank-fusion-in-hybrid-search/](https://glaforge.dev/posts/2026/02/10/advanced-rag-understanding-reciprocal-rank-fusion-in-hybrid-search/)  
> 27. Reciprocal Rank Fusion outperforms Condorcet and Individual Rank, [https://www.researchgate.net/publication/221301121\_Reciprocal\_Rank\_Fusion\_outperforms\_Condorcet\_and\_Individual\_Rank\_Learning\_Methods](https://www.researchgate.net/publication/221301121_Reciprocal_Rank_Fusion_outperforms_Condorcet_and_Individual_Rank_Learning_Methods)  
> 28. Reciprocal Rank Fusion (RRF): A Simple Yet Powerful Search, [https://medium.com/@mahaboobali\_shaik/reciprocal-rank-fusion-rrf-a-simple-yet-powerful-search-ranking-technique-6e29d84a5357](https://medium.com/@mahaboobali_shaik/reciprocal-rank-fusion-rrf-a-simple-yet-powerful-search-ranking-technique-6e29d84a5357)  
> 29. Preliminary Research Report Metasearch Engine, [https://www.maths.tcd.ie/\~graysons/documents/preliminary\_metasearchReport.pdf](https://www.maths.tcd.ie/~graysons/documents/preliminary_metasearchReport.pdf)  
> 30. Reciprocal Rank Fusion: The Formula That Makes Hybrid ... \- Scaler, [https://www.scaler.com/topics/reciprocal-rank-fusion/](https://www.scaler.com/topics/reciprocal-rank-fusion/)  
> 31. How BM25 and RAG Retrieve Information Differently? \- MarkTechPost, [https://www.marktechpost.com/2026/03/22/how-bm25-and-rag-retrieve-information-differently/](https://www.marktechpost.com/2026/03/22/how-bm25-and-rag-retrieve-information-differently/)  
> 32. BM25 for Developers: What Actually Matters in Production, [https://ranjankumar.in/bm25-based-searching-a-developers-comprehensive-guide](https://ranjankumar.in/bm25-based-searching-a-developers-comprehensive-guide)  
> 33. Hybrid Search Guide: Vectors & Full-Text (April 2026\) \- Supermemory, [https://supermemory.ai/blog/hybrid-search-guide/](https://supermemory.ai/blog/hybrid-search-guide/)  
> 34. Chapter 1 Introduction \- arXiv, [https://arxiv.org/html/2601.20659v1](https://arxiv.org/html/2601.20659v1)  
> 35. From Prompt Engineering to Knowledge Graphs — Part 2 \- Medium, [https://medium.com/@yu-joshua/from-prompt-engineering-to-knowledge-graphs-part-2-d567e43825d9](https://medium.com/@yu-joshua/from-prompt-engineering-to-knowledge-graphs-part-2-d567e43825d9)  
> 36. Retrieval-augmented generation for natural language processing, [https://www.researchgate.net/publication/405619761\_Retrieval-augmented\_generation\_for\_natural\_language\_processing\_a\_survey](https://www.researchgate.net/publication/405619761_Retrieval-augmented_generation_for_natural_language_processing_a_survey)  
> 37. The Transformative Effect of Coreference Resolution on Retrieval, [https://aclanthology.org/2025.acl-srw.27.pdf](https://aclanthology.org/2025.acl-srw.27.pdf)  
> 38. The Transformative Effect of Coreference Resolution on Retrieval, [https://arxiv.org/abs/2507.07847](https://arxiv.org/abs/2507.07847)  
> 39. The Transformative Effect of Coreference Resolution on Retrieval, [https://aclanthology.org/2025.acl-srw.27/](https://aclanthology.org/2025.acl-srw.27/)  
> 40. Algorithmic Relative Complexity \- MDPI, [https://www.mdpi.com/1099-4300/13/4/902](https://www.mdpi.com/1099-4300/13/4/902)  
> 41. (PDF) Core-based Hierarchies for Efficient GraphRAG \- ResearchGate, [https://www.researchgate.net/publication/401599732\_Core-based\_Hierarchies\_for\_Efficient\_GraphRAG](https://www.researchgate.net/publication/401599732_Core-based_Hierarchies_for_Efficient_GraphRAG)  
> 42. The Transformative Effect of Coreference Resolution on Retrieval, [https://arxiv.org/html/2507.07847v1](https://arxiv.org/html/2507.07847v1)  
> 43. RFC 9110 — HTTP Semantics (content negotiation) \- AgentGrade, [https://agentgrade.com/standards/rfc-9110](https://agentgrade.com/standards/rfc-9110)  
> 44. Accept \- Expert Guide to HTTP headers, [https://http.dev/accept](https://http.dev/accept)  
> 45. RFC 9110 \- HTTP Semantics \- IETF Datatracker, [https://datatracker.ietf.org/doc/html/rfc9110](https://datatracker.ietf.org/doc/html/rfc9110)  
> 46. Relevant Standards \- Apache HTTP Server Version 2.4, [https://httpd.apache.org/docs/current/misc/relevant\_standards.html](https://httpd.apache.org/docs/current/misc/relevant_standards.html)  
> 47. HTTP resources and specifications \- MDN Web Docs \- Mozilla, [https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Resources\_and\_specifications](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Resources_and_specifications)  
> 48. Risk-Reward Trade-offs in Rank Fusion \- Rodger Benham, [https://rodgerbenham.github.io/bc17-adcs.pdf](https://rodgerbenham.github.io/bc17-adcs.pdf)  
> 49. Self-Reflective APIs: Structure Beats Verbosity for AI Agent Recovery, [https://arxiv.org/html/2606.05037v1](https://arxiv.org/html/2606.05037v1)  
> 50. Self-Reflective APIs: Structure Beats Verbosity for AI Agent Recovery, [https://arxiv.org/pdf/2606.05037](https://arxiv.org/pdf/2606.05037)  
> 51. Self-Reflective APIs: Structure Beats Verbosity for AI Agent Recovery, [https://arxiv.org/abs/2606.05037](https://arxiv.org/abs/2606.05037)  
> 52. (PDF) A semantic approach to mapping the Provenance Ontology to, [https://www.researchgate.net/publication/389069473\_A\_semantic\_approach\_to\_mapping\_the\_Provenance\_Ontology\_to\_Basic\_Formal\_Ontology](https://www.researchgate.net/publication/389069473_A_semantic_approach_to_mapping_the_Provenance_Ontology_to_Basic_Formal_Ontology)  
> 53. semantica-agi/semantica at explainx \- GitHub, [https://github.com/semantica-agi/semantica?ref=explainx](https://github.com/semantica-agi/semantica?ref=explainx)  
> 54. The Virtual Brain Ontology: A Digital Knowledge Framework for, [https://www.biorxiv.org/content/10.1101/2025.11.19.689211v2.full-text](https://www.biorxiv.org/content/10.1101/2025.11.19.689211v2.full-text)  
> 55. Data Catalog Vocabulary (DCAT) \- Version 3 \- W3C, [https://www.w3.org/TR/vocab-dcat-3/](https://www.w3.org/TR/vocab-dcat-3/)  
> 56. Data on the Web Best Practices \- W3C, [https://www.w3.org/TR/dwbp/](https://www.w3.org/TR/dwbp/)  
> 57. The Machine That Reads — A History of Web Scraping & Automation, [https://athree.dev/the-machine/](https://athree.dev/the-machine/)  
> 58. Detecting and Measuring Web Cache Poisoning in the Wild, [https://www.researchgate.net/publication/386583730\_Internet's\_Invisible\_Enemy\_Detecting\_and\_Measuring\_Web\_Cache\_Poisoning\_in\_the\_Wild](https://www.researchgate.net/publication/386583730_Internet's_Invisible_Enemy_Detecting_and_Measuring_Web_Cache_Poisoning_in_the_Wild)  
> 59. Some Gripes on User-Agent, Again, [http://vega.pgw.jp/\~kabe/WWW/agentgripes2.html](http://vega.pgw.jp/~kabe/WWW/agentgripes2.html)  
> 60. Reciprocal Rank Fusion (RRF) explained in 4 mins \- Medium, [https://medium.com/@devalshah1619/mathematical-intuition-behind-reciprocal-rank-fusion-rrf-explained-in-2-mins-002df0cc5e2a](https://medium.com/@devalshah1619/mathematical-intuition-behind-reciprocal-rank-fusion-rrf-explained-in-2-mins-002df0cc5e2a)  
> 61. Linkset: Media Types and a Link Relation Type for Link Sets, [https://greenbytes.de/tech/webdav/draft-ietf-httpapi-linkset-02.html](https://greenbytes.de/tech/webdav/draft-ietf-httpapi-linkset-02.html)  
> 62. RFC 8288 \- Web Linking | RFCinfo, [https://rfcinfo.com/rfc-8288/](https://rfcinfo.com/rfc-8288/)  
> 63. RFC 8288 Web Linking, [https://www.rfc-editor.org/rfc/rfc8288.html](https://www.rfc-editor.org/rfc/rfc8288.html)  
> 64. RFC 8631: Link Relation Types for Web Services, [https://www.rfc-editor.org/info/rfc8631/](https://www.rfc-editor.org/info/rfc8631/)  
> 65. Exploring Network Structure, Dynamics, and Function Using NetworkX, [https://www.researchgate.net/publication/236407765\_Exploring\_Network\_Structure\_Dynamics\_and\_Function\_Using\_NetworkX](https://www.researchgate.net/publication/236407765_Exploring_Network_Structure_Dynamics_and_Function_Using_NetworkX)  
> 66. A study on natural language processing: Exploring text and network, [https://medium.com/@pedro.henriquesantos1407/a-study-on-natural-language-processing-exploring-text-and-network-analysis-with-python-and-gephi-b0a8209aded0](https://medium.com/@pedro.henriquesantos1407/a-study-on-natural-language-processing-exploring-text-and-network-analysis-with-python-and-gephi-b0a8209aded0)  
> 67. A community partitioning algorithm for cyberspace \- PMC \- NIH, [https://pmc.ncbi.nlm.nih.gov/articles/PMC10624825/](https://pmc.ncbi.nlm.nih.gov/articles/PMC10624825/)  
> 68. Run graph algorithms \- Ladybug, [https://docs.ladybugdb.com/get-started/graph-algorithms/](https://docs.ladybugdb.com/get-started/graph-algorithms/)  
> 69. Graph \- python-igraph API reference, [https://igraph.org/python/api/0.9.8/igraph.Graph.html](https://igraph.org/python/api/0.9.8/igraph.Graph.html)  
> 70. arXiv:1606.07550v1 \[cs.SI\] 24 Jun 2016, [https://arxiv.org/pdf/1606.07550](https://arxiv.org/pdf/1606.07550)  
> 71. Syntactic Multi-view Learning for Open Information Extraction, [https://aclanthology.org/2022.emnlp-main.272.pdf](https://aclanthology.org/2022.emnlp-main.272.pdf)  
> 72. Spacy Tutorial \- ismy.net, [https://www.ismy.net/archive/spacy-tutorial](https://www.ismy.net/archive/spacy-tutorial)  
> 73. GraphRAG: From Local to Global Query-Focused Summarization, [https://beancount.io/bean-labs/research-logs/2026/06/04/graphrag-local-to-global-query-focused-summarization](https://beancount.io/bean-labs/research-logs/2026/06/04/graphrag-local-to-global-query-focused-summarization)  
> 74. A Graph RAG Approach to Query-Focused Summarization \- arXiv, [https://arxiv.org/html/2404.16130v1](https://arxiv.org/html/2404.16130v1)  
> 75. A Graph RAG Approach to Query-Focused Summarization, [https://www.semanticscholar.org/paper/From-Local-to-Global%3A-A-Graph-RAG-Approach-to-Edge-Trinh/c1799bf28d1ae93e1631be5b59196ee1e568f538](https://www.semanticscholar.org/paper/From-Local-to-Global%3A-A-Graph-RAG-Approach-to-Edge-Trinh/c1799bf28d1ae93e1631be5b59196ee1e568f538)  
> 76. A Graph RAG Approach to Query-Focused Summarization \- arXiv, [https://arxiv.org/abs/2404.16130](https://arxiv.org/abs/2404.16130)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAbCAYAAACqenW9AAABZElEQVR4XpWSPUoEQRCFuxkFMwNTDyL4lxh4AQVBEwMRNNADeAuzzQRB2EwjUwWjjeYA5hqIGJqsX1XXdFf3bGKxr6te1Zs3Rc+GGAOhhwvjMpSfwfqZealrNUXUBxIrJi1JsgX14DyY+XDMv2V0JoN4yfkJ5jheq6tH0iZm/CyKOMQtG+usDnFPvXuKb3I3FqQ0UBF8gIfs5a9TxcZJG6Q5ONW1YtgmT+EzsJttbeMbkojXwTk4YcKD4Qdc2B55mRdyD67AgRntgwl8VZlGjGuAWxDnOCPLNS7bTA53J/8Sh3AIlX13GMrO7wjudD13IxrQW9IXVSdD+JTUm+6Y/l4Sprf0FE/l8fAInkEX5UOFsDQssoL6F3I0KKk3OV8p34KsVgblzB2jTXdxlKu3uiqUlFy7NP/L3PKvr+xNVCKJc1+1jSoblOXc1KjMvEbWKHu5DdNHqjrVG9WoXWEcSTAS2gp/B74nzLw8I0QAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACcAAAAXCAYAAACI2VaYAAADOUlEQVR4Xo1WW4iOQRh+h93WslEunAp7w4VNS6xSIkpcCCmUJLsXCou4c2HLXiGHIndayiqnXMgxiSjChQtyiNhIDim5oUjreeedb745/v/31PPNzPMe5p355pv/J2Io/RRU6ScEParp7yIRm+h7iJyMkA2ogCg2EhJStNJ6yFXr52iEcBHSRM9YbbJT4IxyqCqEUC53JDCOgytDsRIUjcPzKTjeT52Yp5QSRoPAZx14yZdcqFjS8NRO8KorpDAZ7EHcHbTvwIfgMyTqMqkOor9A90QYAn4Cl4o5hXRpAZrg9R3t7NBQYA/4C3wALkHSJqMPRb8XwU8wD9uHaVXmXA6+zW6OC9fD9APpJJpzwWL0oA/NINptrsVBA/gRvBbop8Fj0q1fHyNRY4Eu8C/URhmKdTuaQfR7Sj8xBsE3wJ1isXgNdpfDGsjVXu7iFOI6iDoKZQweP2F4Q/o6qIl94FQ7UjQKD062wmo+5sLnFnweoX8bnIN+H9oz4G52iHZR8c7R2sJwGBxUZkfySCxbUbspbn6gM6aTvPIWo94Df8CIGL1IjmsxBbn4CmFLMXhJ4jiztJNdRh10mOK4ELL+EnsUj0kiaOUDeN4MDuCxydhCvCL5MIm/Rk7+m/iLzNUi+hqyt79FsXPtdRbTpmSeTh64XmXf9l6Ae4vBAMlrbc7npuEgzo6+01xwsRxrXmtiWmk2kxTX6lg0Emv6DO4qtF5ePfqr/HwWoyFcRrvIlzVGkBS3LDQA64lzSzKO5w+uQCt4xBm7+IcKVhcDPrA3SW55/2CTmkdyfTg/yg5k4vfgDt/Ax0VhEr5Q9Xn8A943Nr4v+8FZZmyhpGje4Wmu3gDDRrR3wccknzrfeRtU8WtA5s4LtpXkauiPddpPsrDn8FmI9rpQ4ecPBaffEl8h/EWHx4eSB6CEq3s+neA3SDXvyDLCz+9OieYQyb+bOnBXll5lgZHgFxj5axZk1+Eg3gh+ewNo26Kg3MoqYit4hWOj6MQiM+Df1RN2VNtXkEsa6HxG8H9OLU4ZK2AsyS8IX1lUxkY5IsFffR7N4AVwQmiwiBJY4SyFN0Lkq+GraZ+EnlhAzQ2MdF/4D4NWcNaEIkiWAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAXCAYAAABnGz2mAAADa0lEQVR4Xp1WW4iNURRee1zmuMeD5JJyKyQzD/IiMiUehDx4mKQZpZTbDFLz4DzMEyUPLjV5UBqSS6MYho7LSFE8SsIwSoOQ8jKexLf22nv/+/L/x+Gr7/x7fWvtvdfa/977/EQelG/8FbVF+1FKVe9jvdWjHHLCtKTsIwdBOgXt1AyR64zF0I4T8pqjwKvgrEzKQzw+HYKyNdfjUOwJUBB2GtwUi3mLZiWz7nXgA1irnRKGFU5oEI1qDbGbwR7eRtXGyBLKDJ2KorlofkRrggnJxWywjGhUQe/AJ+BzcLvxHwNXmTaguOIhcF2m+QhTZUsSS0q4Dh7UrdRHh8Fh8DG4Fqw3+giwE+HP0GsYI5e8rhvAAV26W4UQsS1IVBSuuMDRmSQZngV/g3u8uoxf/44EP4C3ModGN3hSmrZPukoxAk2MeSTzN3ka7TViOUgpXdLbYLuzxP0K3O00FoN+yRiCqHaDQWgHrDEV/AG+IX3k02gPR8AFnj2JpKCN2gq7LgYvgvfAFu3KkrkEtlnD63YHPCXFER0nGby9ek6MOEAtJem70iny4D35CJwMHgU/WT8wk6RPq5jBmJwwF6PxkiSw0Qrx9AKpIlKWkfRdYmyrc6IdJO/0NXjTuBh8urnPfE+zOANWuFGvJOgnSZXx3D62kL7V/Qi3YvwMXOaI8hXC/mZv352jcAV1pPF2Iey+1d8Td1Y0xgo5GAtWlNzSZFcPk/PfD/eVVymyD+wXvX9Lxq5DACd1OVkAEfg1XrNSJ1SuarMVQqgpJJdfk5s2G3UcyYqst1I04UPi6yUTG81cfAvkoQ88YdpqPMlpGFLeJjaDrSC5IhqcnmIQ3BeL5tVdAO9aBexVUkhDehNp8H7c6Qt8ebaA/eBT0gOqMobaBpbiZYjAF/P5zAyCZ5D4bpD8mwyAX8ltCQbH6x05jSTp5ZnPuF2jeiIBENoKfiH57Ilf8xynKW1/R4MLyQPfhS9i0R2af8jJYiL4meTU+uAVcqcd2I/Bf2EGdy252eTBK9uW+WpOJczcLazYu/DojcZ6C3aZkIV4fAN3+AEe+E7jLxh7eu0ERckV6Ql4z/SAa7w+/HXSDbMC9pP9c06gP5v6ELNIW54jp/Vf4HvwCjhdWzUNpoM6lBy8FAVHN0QcE9sJigO0x7pzwv4A2sh7yPTHEKkAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAXCAYAAABNq8wJAAAD5UlEQVR4Xq1WW6hWRRReY4ZlUmJQKloHxXxQSUlFUQqFsAfJ8MHwgnR8EERN8qkQFXwQFS9g+BYmlJYXEiI1jVAUFPVB0PCCogc1zBLEF4NEjt83a/aemT0z5/yH/ODbM3vdZs1lr9kiTZimICNKBM8ZpfgleQWrT4wSwf9DK+FasXluiAd7EYIDaIdG0gzyi9USdoFjm0KPngZ19q7Zgd4nXtlzlIYPJjwQvAAOCtQtoJvIaObh8VNT3SW8b0ae6Xu0g4cassjrbTzWgMfBm+AZ8BK4yBlshs0Hrk/0gvefaD8KZA2Us/Jv+Wwz6AM+AMc3FcRq8DF4GpyBoDRm7BfwXAeed/qXKgfgY/CGtSrCrXTGojS1jKkE0m/BvYHCYifYCS73oihkbzzugIcDIfEd+HVhxFImNRJ1aaYxeBqehILPRZPn0Unh4/0KfuEVFtfAZdrtduAE+VXPfBsWtXyEaL4Wb4CPwOtiS2EGPtoG8B2vkNdEA80qjDgZ/A08C/4OThTd6d3gVzRwbrNAFgHu7iQVWQwQ/f4mVYZ+g8yTSrZVNAm3svlMasRL9q6o7/uRUgcYI3q8+qlQToIPQfpsgA39qBsJHnQ2/PZ+cH1iPuJ0ItwwfY0Gv1/1rogmMc4rK8ST8bOvMUHUl8l6qM128K1Achvc5943gYtdfxU4BRwuGutLJyd2gR3Bezj8Vb6wytDpX5CVpivMMfUtW5/FagfYJggmPErUrt2LtBcktF7UZohqLDBps8ebRLhcdTpEHV+uVSn6IhDPcq+GHBMywREqYonRMdqaigAXhd+LyxzNaHFVMZxwgHtVh/WdhrO9LsIA+P2MdnpTAbwi6juzqQAWGI1N0J9FQtyqt6GzzekI3is86/bDdlhBmZT/fZ5WHX5IR0Vv0+ZKThUtnTZINP8a5pboYPqmDY6m4QB7IeD38R94ypnwPvkefM+9E9hZcxftWhegv2g+/1CXGbdNdHI1esPoM7QnwHOGZc7YO2GhxLeuQ3R2WRaZUBMbRSf/BzgNPAKnI2g3m/xHz8VjNaLNMaMrvL+wbJ+KVjQp6D2sumubdvBvCe+Q0KnkG8sHg68H75xMJ2wYWxHbbxH791uAty2N7qCJvorHX+CcWNkyeFnx/4q7VeEgQvNo+sLi14NHsEO0snlFl0i2IXFaCv7SFIZIFsULWP/5X8PjSswFHxq9Y3Lgf9A3tpeklCSaQWJj+yyv/BX4sOSdl9eTWYkn6z1va97Ew/LDyJtCG2PLeqCMViXsh0gETXC79xs9z0J775Fm0n04ydn8KHVZrZSpkSIjz4gkTjRGSd4zxPHD/jN7WZPqz2UVVwAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAM0AAAAcCAYAAADC3jvjAAAGOElEQVR4Xu2cWehuUxTA12eWoXtTXIkbHlCKzPNFN3OS3BdP/3sfUB6EdCMlJQ9k9kDh4pYhMsuUXGPInFCKW+JJpgeFdK111j7f2Wedtc8ezvh9vl+tvnPWsNfa+5zzP9M+f4BaJsqSSzFH9NW3vvIQfeZa0JQxbC2tBk3XNZ6cillRzRfTDtb11LbV+S3w09H4ddSsnx4Th6cK94yny7bD6byKzhO0ilKtoppv+ugw5+giU2iboX7zR1LPk4KaM1DaoZi57pYK7rb641BeQ/keZQvK+2Vzxsso/wDbf0K5vmyGnVAuRnkR5VuUj1A+Q7kNZWuU81GunnozhwHn/QW43a/NOskmlD9Q3kQ5xfirpA1NWtSC9hjtFogs7BWUzcA78FFlU8YVKBuUNs9F+QE4dglleaZlxzOBD6B/UVZlmiqPAOfcW+h3RnkB5S+UE4VtfCgDoxLq1xCZRq57iQ4wOOMUg6IiHGo/yYFp0JmC/tIvAe/AT5eszN0op+Yrpr51wP4bUXbIbQI6KH5H2Vbt1CQ74D6XasPuwGect6WhD7RyW8WXwGfviIHSJjBApVbK01DuRNkOirPNAYU540Ngew6djf5GeQllG0svuQblKak0HIKyBeu4SRos3gCuZ0dp6ILJEBtiHuhz2AJzBboFUm3tZpTzzPKVwDspHUQ5K4HvVywm74B+cEkuRFmjJUWuAm7jDGmwyPPsLw0WK4B9SjJRdJbQH4qWUPsWTTutDMMs1x5IpYt037GrWaZ7iZ+BL4uWGd1FwPc0OXSA0Y7nOoOE8irw2YpyluES6QxGdVCuvL45prJdVMK8FJIDG4W2QET2CNcm7IHyltDdCLyj0lmHeBzl0NyIdd1r7JflugToQKGb/NelwWIVcB46qMdPTxtsKNK6J6PkeixN49uBLp+uFboVWNqf+Psjyi4o3wj7JuCd+QShlxyIco5UGs4GboPueRSywbkL2OeSsm04xrHJ/s+MYwvcB/yuxiIr7B7gHZaejJHYPGRspwu95FGU/aTScAdwG8dONeXx2Af4qRudZejpXh3qPU2tTGB10/Hv/6GBlk/T1VByj4xtiWGytsK09K9Af/pFZ4l8J1srbKuNnl5eatALzVuhuLzToJegv4Gem85u76J8CfzYuRdmeGOOD2swaTFmbGN8m5KS6yyUT1EmjuAngA+OvaQBivueS4WefOkBwRqht9kXOPY5oacy6F0QvTPaiGvVBwRd4Oh8EiFthfgMRlHcWMtsq67YduhehC57zJlkshl/Typ5MHTp9IVUWpyM8izwgUcHwA0ol6PsafnYHA88TYeemFFumpKTT50hoYPlAeCDeTBiB9Pvr3vo2gVRjGIQeyiihxSG/jI5yUoYQR0DMf89j+xhpHsavSSxaS+hsyWnIQRHsEPdlKRmKSgpsCGd5gxuPNhxcPqotM0cRVtprWpRVV1VM7O00BVfEz57Gds7INLn4rMvGDM9bL3aFDXGGlOryDxyXSXIqXtcZbj0KYS2lfmFOreAP5XfI8xn5FhdGEdvBqoiOW1y4KwyJx023ZiT3gR0xOuQvej0etU40MvLI6VySk2gJMK1ih5ML2mn3xDFYJqrH5vCkv6I3d06zRX0vRimcae5hz5dhUraisKD099paEhX7RoimqeNLeetOalp92HQZjr3Qk1V/MnEMVKpUm0mZmzoU/DDpbIBNAXpSalUoJnjNPY+XQDVAQgiMSyOXpJkHAQ8x+wx4J3nOuAXoGuNfXvg/wPQxsdhB6PcLpUtQ/PrvkPZTRoc0ItdmhFhMR38FsamtCHpq9fngc9sPjD3pC43QZ+JT2elF6g7D83ouEDqJlVde6hlhNEgtAtK5azH1Q/w9whLR2/z6S0+fW1JLIF77lkART6z9B7QJ9FC2SJ0yUEzqu2vT+u4H4ugfwgiWY+SNjayT9Y6Lt4C/kvBcm6Ol7lXonxslkOgybDy84yqTtaeRM0UV6dBQ3fWtTVEB7ihD87or+QypdFP+CczPAP8PwJ0qrE+HkQ5WiqjMXnpJ76EKVuh/ArVr0WLsalixgYocf3Y6JA/fcnqIiw3T5LdYK2HQJN2qc8VXc1uHoAj1qF2EutvI2LVpjJlYRGrGf8BVXnbVWkaU2YAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFwAAAAXCAYAAACGcCj3AAAEpklEQVR4XsWZS6hWVRTH19YUxZRqYHqjhxXUIDAaKObNHlj2TsUmQVAOKmggKQ6UJoFEFCQ9oIQsboYVQWIUvajsIYoIqUQKDZKiRhHVICiJ23/ttc939l77cfb57mf98O85Zz332Wefx6dEDtPseHt2X/4E6OPeJAskjYqaGKY2Lkcpv+SrZcga/dLi6NjSlyEqVKT4IRXhpKPqcgLKKdabCEmYOujO6I7w0dH6uERtbG1cn8guokqR4T/G9W+GYUYxnooaxRBTdk8FLqzLF5sVnR61cRFdiWY016SLih5XQx9D30OT0MHQbfkAOkXi/xl6LHTTHOhB6D3oO+gwdATaDk3HINZiu6UNt1xF0vdXI3WPu2PI7MP2D+hz6HoOrjiPWi6C1tTWK8WVfDV8CJ0kOfklvsMWNrQRf78yMLTd7oR+JMm9Dzrb891CMvn/QNcOrCG7SXqer+xnQu9Cf0HXKJ/DO+Xu5XsF9CrJ4llVnK2Srw+FOrxCjxuZMD75PWIOMp6HbvANYD1J/C5olvI17EaV37GdoR0WYy/W0dhse8/HHq/0L5W7THiil0GvQZ9CdwUe0qFDMGSBm6BnoZnUrnIeqM8h1J7p1ee74G/ofeiM1uxjo7di+7b2OBbDx72e1A6Pz0jGM1s7OliE7hMk41tqLaZyfqqCUtQnPgWtdvGbSE6QL0DDhSTPZ5+vKH1hNPdAd2ujYzNJjZu1wxt60+eS1uQRnKM9GINeIMm70fcmqZ+jPqEe6azDsM9z+/zs/IXkpXWWtRh6AGn8DG9YDU3Cllu5A9LtBnxEcpdwzxR85/A4eMKb8SkGHc6BniB5dNwxsGYH0Dhk64dlUzxqYnKcC32hbI+TnOQmV/hN6EqvzQ7n39AYuggGKAc8yfxC/MR3WVywkRftJHb4xetsJne2/D75AVqbC7B0v1xDkuFsTDoseY/At/yjyrYA+hP6CZoLnQjdtI9kwseVnVS7y6HbE3bmNpLn91bt8HjOxTzEB22FqFbDGFw74T+A/TXaGZEto6iIi0IiQ8tLJN/imhep/QJh+Uw43ypl17wOXWz34gE8Q1JjmXY4LiD5uuHVzV9RiRJZLiUZ/35onemVGtP8wAtvjrBknwbfEj8rOaPJslvDq5MnhHW/8zSsdHb+YaNHwkyHniZ5AQtSc3BI8gPpN0p/4fBdxZP1DdlPwxJRbx++U3kcfNHuhab5znjYPkVnmoqUW6GvKR/6FsnEnqcdxM95Y30PNwZXhGP5ZZr7MmEWkdR9R9m5BH/r869OvqtyL9NeGFnxb2B7jOQROi17xlmahFJi3jdO8iJyK9icxPEKHURyu/Mgw1rt/nXQXpKLxpO3DXoEWjiICFkOHTTyZcK9+Z8J3M95K57ol0kWwgiIJoDvWn6ETtijyM2kTzR9PApyNZU9PNRJ+rg/bYVmr1DTFL39qWj5PzH6EUnFVN34Emi6I4ZnShWnlDwkNT3jmH5TGMbUZFQwojI9MEM1HSLFkclMmWttp5tEz4QpTRwYW7rJrMzOUqmAlC1BZViKKaTWkW6QtqYoRmac+n+HAgqu00OqYcrWEnpVbJRqAtu/PO+fObGTMekAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD8AAAAaCAYAAAAAPoRaAAADoUlEQVR4XuWXS6hOURTH15HHwDPllTCkpLwSwkCS1C0zchVKDAhhIAxImShJlyivkoGUR1EuRddIuiLqMlDuhIGUGDCQrv86e5/93vvs77vfdyd+9f++fdZaZ52117f3PvcSZVDYH2osrxxsazimSXvsuZ4hB+cmb5IeNXbP7RlqTIGJ5WDe1FT9FYO52XPHJhO2KrwaAvGeyTMoPI9niJIfKQjEB0wm3lyTZAdmkmxy0mlTMwvtyYmJYUck4wPOgEmxHHoCfYIGoBfu5HH1CIM/0v8FOmEElDH15MREGQM9hl6TqOEXNMmKIDoJ/SDh/wk9qBw5T+5GUD+VNxdLXCc4AF0zDXaLHDxDHsnbCjpKqkY6pKL1TYupbFAxVllcdKwajcb4Pb63kUh8t3IYdEGrXaNFma78WAPFCyBaAM10jRk8g1ZBf0mswFG2mzZCx90WJhsK1kLnoJGkOzvbDAAvkYb9cfRTlkL3oRHKQuotsBLqgcb7VZlvCjnWBvxA9EqOb5KocYfyCroQz81piNPQBjk+SCIxN6NiFvTQuE4i6+V8vE3MKU6l8kyhaYYtlw7ojBwvJFHjG+0ueQcN54HX1xAyqBcaJ018uHwjPjQKmiBtO6nc82bKnPTFHnxc4AGJA+opRvPsGEkstR7zxNcb9m4SDeAtxsyh8HZNVjoFeu6EnCKRmFcBcwuaz4NwXUn2Q5dI7Ffe6wkCGbWJT3r+YSrWkajxnrzmRu/V7gonp3O5GTpmm8rlya+TzyQOrg+2mwkU6lHG8BLvw/g2vofZ/mymk3gdu/QWogGLoDvQXMdfy2US73qXiyQS35BKEmkFN5G3FO/RXYi5TrHQ5JIqtuLjsG0qPzvl5HnifZZf4SWrKB18U+iQ4D2ExAUn314Zo6l8JpNYqh3GTbsxPo/vIjlXH26++tvDiOe6P5JowFVtzoMPEC5Q57Or4qXKiXnZ1aPvnUgib6eyaOcRqt4k3qw9AzMD+kr+X3QVvM+5xi2uI8YKEstxQC6bfhJ/PLjPXwa9tSwG4Y6VnIU22Sbrv70rhT6lLcoYEchnTQ/Gv0nU+B3ap91qxO9/bg5vscYwE3lTCOBN2KjWsmdTEx9zx+yDoqmk9k3hFGFrM4RbHaihdY80aEtSJjABj/DUbWJ2CrikwbO3lJyJ1TAkdVrknQWaxqIbp93520JN0TXu5nF+PH3R6K9awxAty2T+pPN/wmxEK5pirprW046cNv8Ah8R1E7oBRSgAAAAASUVORK5CYII=>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAWCAYAAAAmaHdCAAABm0lEQVR4Xn1TLU8EQQydJgTDR5AkCCT8AhIuBIFAoNAoMPyAw2LQuAsCQYJAIlAkEP4AISQkCMBxBhQKgUEcr9N22p3d4+Xamfa9abuzeykZiH+UN+w11doVnmKuEripb6QaB6VOkFaM7TmsDmpFO1tYl5mgPijOshY3krl7jP/BPxqZAOjB7mDvsBHsPiq0wg02vyT8J+woSsKabmFDDDhCZsWuxQrh10fu3MQKsidiNwX/CtuVbnSlEnOME9iGBRnVRW4iGmCdxDpMXIjSkgqtzgNW5seA0jHIbY0OYPxIA+uDZRH+2uT6fPocXvYRNquCaaS/wH0jmFN+H/m+6OuPQcId+MNmPs2D+0H+A/sZ2FthKHxT/FXql3gG13PChqTTJK/0Qm0c8sEX2IQc9kGxW078uon4be0VwiG9gC3YkzZ357Uuk0yzIKH/fxhrSS6TBWxDEOsidEC6iuU5JsK/2FHimsjwvi3a77dcbsX64B3HQ23lOiSltZWPjVzfaO5ST+ocnR0iWoKY6CjcVbVVg+GD2CwVMpHxBy5zLgr6vkF+AAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEIAAAAXCAYAAAC/F5msAAACvklEQVR4Xq2Vva8OQRTGZ0WC+IgCN0Hjj6AhGo1E5eNGVBr0vkIlEp1C4h/QoZOIj9wbnYJCpZJbqVWEUGiuZ3bOuzsfzzkz+65f8mTnfc4zZ3Zm7+51zqLLDbHEJ+WZpI3jtUYKQ9B8Qm0TzEuJE2m6Plcw1k8ha5mTSN6k01NqgaIdBOlCLJOpeRPtPmMSl0SIZWLm4ydgBpem76q1lqJWbqJ5ciVYKRc0Hxwpx1YxJvmGxYo2VXiKu8v0b2FWp2mHQiB7IhY3+nGaKPIFJEGsEXJTNtqEwhA0fzrF2ciIr8DdgUrZppg89SnFTEt74s2bmGWzKGWeuQa9g16jfhjXt9AH6Ct0IQ4WkH5dmLOJ0WbXX0uNfuevf6FdQ4MY3n8eSoMj0FNoxfkb69wXJE9I7TL0Czq4CI+HqXRL/DQTT9Nmm7RMaskIYzSMbkGnoJMuPKUzUd2Pvbcqzm5oAzo0ZDS0GzIPcQ7pCc9Z5h70B9oZeXdcOIjT8nsLdNVp3y6NaelJ+XjDS22e5N9Aa2E47PSVC+/zvkVIygXZTcg3QvsuFPqNuXtk7kC8DFlypBLk5expyo+t0A/oblTa78JfyCP5fR56gvxttlgdfjvlrzpavve1YoyROebCk3nmQsy/As8xeo/rdmgHdMX51wKHsZjE++mbjJ9GZuTTMswioZI3yjdQ/Ynrfegj9Al6CG2Tuv9I7oXWobPi2RiLeXhZP0TN6C1yrpx64gW0psXE9/9Cv0H+XT4QlZ31aLWeczB7kiKxHHP9a/AdepAXAsOE69Bj6CJ0PKmQpjW0GZo/QhLEWoajLnwfzuWFjEvQS+dfn2Jh/S9Co5ghRjEWikNvW2akIb+BkD+Iz9DNvNgGv2Xd0netRU1aMjFT8wktk82MWRS0TOprqZ74cAlqRSto/vL8/46UYpnCIHTuH7PGSFsPL0enAAAAAElFTkSuQmCC>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADQAAAAWCAYAAACPHL/WAAACAElEQVR4Xq2Vu0oFMRCGk0LURry0FnZ2gr2g1r6BpdjYCiJoYSUI+gyCWKuPYGFjYaGV7+BT+O9mk03mksue88Gcs/nnn0ky7FFjBmz48EKyiJ4raLTPhLwXV7lCyBqyySbiQYeuZNbl3XKOJCcZO83pZN8s1fmScRLJ66hQMTktP45kXE8jU9mnMvkS9JAqVaZqW4xWIuiRJGSb0YcniiJHiA/EPk10Pfh0aWO6lrHBV+eXcJVjp0hkHCDxjnhCbHWCVJROb3S4Lcarex/fK25US5OZcYz4RJN7tNnwYtxSba8mHGSuKrKr6gRZ9lD4iNIHPG92QlUbYqKXaOnRf/kC4T5VvQR2ES+IZ8QOyRURzkEUrs4ZMpJxv23EK+INsRTUFnJnDzlqslzyaLpLkIukrEG/w/cf4tYkJvdY+l+bpNmsKikUpIeSzcuIC8Q34hKx7mTZLEN/RQPKpbo11XQ0Z6y75wXEGeIHcW7cxUIyoO0uaYbK3NRfncphD37IPM6ziDhFfCGuESuRI4I2pOuBQVayekLTTXS/6EnGmhN8/iKujHoRgVzPHmIo+mdk6H9orb3B9yrRJ+P/SLT0afFyKqrLFv6Dp2vOhJsOSCVucPN8C7TzMcEMmlbg6RJqMmnB0HSPlJc0Rj82W2luJNMzkxKgbn/oqUwspy85bfEPb7kUTm20UFAAAAAASUVORK5CYII=>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAG0AAAAXCAYAAAABQcHxAAAFcElEQVR4Xs1Za8hmUxRe2/1+a8QfpfFDJlPu93sR4w9JUYpEpMlgjFzziRLFKJdpZBiRELk2hRiR+10uMYOJJCW5/EIaz/Oufd6zL2ufd5/ve99vPM3znXc/a+2119n77H322SPSBZcKM4QLQ443+HijTRA+0f75mjVMcYhua4JezgUEMcrhypYU9Z5dGE+UCaGQXEEO4WqcNhAmn1lw91WNGU6G1IVdwRWotRrXd8DzE3sXrgK/Bl8EHwcXNIaeOcwIs9JW1kgmiK11oa+/Yg74KXiRL+8GrgGnGodSWKd17gI39dIUuB48vfGJaoeBjKCZlAk1KFcqW0Jbl1cBUZW0flq24H0KrpZ8m+ighbgQ/EXawcjgA7Hen+BcLx8sOmirO++jHw4FD0/FfggSiH72T6xQY3tYzsF149QQolC3xdAh9UzLIuvAxxLtOKedf2Sip3hVdHB392V2Luu96csGnJWDhQVw43J9LzifglXN0mpQU6/Lx9t2Bm8G34NwHq6bBS6KriBimy0tBN9l7OTlief+Xr82UnMwyV2C8sWi9a5vBDOBgWhaiJPB18CHnJN9WrnkX9IblOwlvYDYfSfRwfoEXAjT5pG1b+yeOEC0k/leCsEnm/oDoxMY2uc6nbUrIW3S2qtxDPgyuEz0vZpgVB4Nav2mhe3AG4UzS+QMcKPYPD6kdxEu5UeLPWjznOoPJ7qFbcBl8P8R1y/E7PAAaTY6q5+H4VFc90yNA+R1YrjBP64ay8G1KJyKK5erj8HPwWfBrYMafbEleBn4oejOehoPZXwTo27JhtbiSz4YtGGovbz+YCOE6GgQM1N+A/dNDQY4QI+Ivk/nNzF731rrch8K83C9UzSHe8CtvNMauN2uP733EJkQghuxC0Tf0QulWQZ9lc6aE0DTHjuOg3N3KAJ7e32plZileWAXNaj3pWTrfAZ26tviNxllhK0VW+au7Tn/+wXJN0Isc9Y1uBRcGpQNsC13EP78AC4Bt4jtDQZ+qThRzEF77OQViX6gaOdfF6l5bhxcLo8h1jqte2KiW+A7lZuOJ2Tk4EnQfpxIUGLH/g3e0EqD984f4OuBxnY5IDXg0ni16DJ7iQSDl3dHX7hikII8BE8znky0k0Q7fni6YeA0cL3T2aLQlr6jDp4SaKPATwy81+QpMZdWI4ghAYeJth1+qhziNV0eq5F16I7gNeBH4GKng5khrGKnqLBtuZoripvAryS2L0HpJ4k/rtkRZwZuZ4t2RvgEbyv6pP8l+g3TF9zic+BIzgYppy2W6QrR91mQt7sVf34X3SAxP+7+XhE9CcqRx2yhNi77i8DPsKPjEV7FBqdmKEu6Acfp7uQNaWaGPkGcfWe1XnRzPPngIO3nNS6L38Bwri+zo+73Pper1CORGMeCb4GrpN9pyDOiD0zzfcdlngPG3STBkx4ub+ukPcXJUJn1DuAt4LfCh8UNHohZBT4W3ZW4rnR6AtHcZHgHnFE/i35YNuDTyw3A93DkssGt9fGBPUHeHQMlkYPiCaID15yLdoGbkV9Fd7AviX7zMecjAh/mexT4fqB1omKOcMZOge/K6M3XSLCNtp1Ci+PFrDRSgj/Fce37zE6HnwSLxfietN1T1HlVoRiqaOiPulB1XlXoF2oR/P+RZIOgIYaBOBu5WvDo7Y5GzBA/7oU8EtH0CdGeaQzDm3W81bRF8B6jHWtcBqj1GyOeBj9IxQRMi0dQHLDRnxiEcSOGNEDt/xrUeXn0ct6gKGcaWbSwh+g77F/R/ybi7+nsXIuoHYwuMEI5iosc4nss1xqi6FI09EBljEq3DiQRwuLMg0eoCVfjU/QqyC0yh0yYOMbxVP/fkN1RJtTjP0z2rzQoUiCLAAAAAElFTkSuQmCC>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABwAAAAWCAYAAADTlvzyAAABkklEQVR4XpVUy0oEMRBMfK0iPtFf8Vs8elC8CIrignoRPIg/5sEFRdCrF3/Empmk089Zt6Am3V2d7k5mZ1OqyGRJ2/NDzEt09MxiQu4cPZRJ0ChJveTpHbTomjnuRbZsELUzQnhiDrdhhJETtUAJltyWkoU81nkYvMZ0UwFRZAc8gbFMkaaN9eMQXSMcgs/gDDxF7hpddT2ht92LDWCK3Lyfh0af4AWESU2piHqF0AOWdRt8Amd4Y8dYl8bLelqp2kviQMLZwOMa1jt4Bq5UwWwkoIK4Xw7uS3sVu85hvKb+6tJEfA8BooxyNnp6OAJ/wVukrLt5rQq5ba2ijFYIj02C60z34Dd4lbrGAdSX2MCd3g7yFPbAB/ADvEnDIKqY+msbgjqwMCYocYn1C7wDN6tAw+egDQVLwniSwS74AvkH6xTcUnoIU9I011dFR+lxAOsR61vqfsUVRTbFF4VfwEblTPbdSp1sf0yT3Dt2d+T+A9nvLTq3U1COTXZcY9jxbIQj2Kc38T5yZhbg8GIc83SFP0KUFGIOxOWVAAAAAElFTkSuQmCC>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACEAAAAWCAYAAABOm/V6AAAC20lEQVR4XqVVTYiOURQ+F2P8ZjDlZ4FZKk2ZbzIppbCwRJLSKBRlIVnYDKYpklBksrEyJCzMMMrPoCk11BQaZVaisGBjISkbnnN/3nvu3zcTTz3vPfec59x77n3f916ielCxw6Lk/ycoO54dVNolTKwPHb6XCCNk4pNPZqhABbsdzW3wGNgsQhZaPQe8DE6NA85oyfgZ+9FrE30e6Aw0HUJVA98hbRnaLeAncBu5yZTO2Q6+Ag/Hi1xKnKRoCIF+uRNC9hT8E1BRH9rpXqK4f1EkPQEPwn8N7R3wJXgLHCFfmMYhcAx2L9rfYL8PBhv9DI/X4HfYj4jzbFioxmEfdx3Y5/DoqDRGeANNq9OkUPQz3IkAvKoVwcRpEWNgt3Cch90uFPvA01W0ABRhdyIFXhWK0LCvKa2Wt/2C6D8G51l7MTgKztS9IDccrU4RagiqPTAGYL8h83GtjTS89R/AheBG8Ir18wxc4KZqASlkEarwTdB98KQxtf8S+BFc4KV6gp0whsFe2DOMntaDV60t4MYPy6pThGqNVrCSzF9ySjqjghjTQP6om61jLngWvAmuNhILm8evYyDjz2E2mSLeyokzOAJ/p6hrGNwLLgKfG0myE2ERFnzgfAV3mG41IxfxzYnE6h1a4ODzwYG/iR/QTLFDdIoEa5mduJtZVA+ZCbuFrwka9r3Irt9gEFwu+l3gZ6Ff5U0PLuJe7AS2gtfBBlHcOlvEicrjF8PYRfpVCCg6iscXazOSIhoR+EXmeI5vJe49BPXpR7yd5m8ZJ/ffh2hC0gOqLqjqXNlMZqHOv9vNs4HMmc4FuHvhPZnDiS8chyVk/nsuchS5fRhgPgf866t2gn/fml9HVUQDniOwD6CdRfxhSpGEHK+EcKMCrCF9uxbBN+wgkvgeqsXJFepMYJH3Wj8fUI1RIFhYkF0MZB0ToDRYaRypd5662sjKIgmHBSV1JfpJoTTa/+EvX7Nwl5ZJBMgAAAAASUVORK5CYII=>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAAXCAYAAAC74kmRAAACZ0lEQVR4Xs2VrY4VQRCFuxEoAgkegyCQgOUZEGQFQYBG8Bw4DC8ADoIDtZ4Etas28AAYfjwhwWCgevqnuk9V9c+9C8uX1L3T55zq7u25M+vcmeBR2Iu9ZturObD3BEB3vq65wYlxtmU1XzHVSiGfg03DVPc6M2ugjONdaOfQZtQ0G0zjmJXakamM7QDTQcBPHME02IzjDVXcEI4QmIdUn6l+Uz0NQvhDMM9nHa7QzVj6Or2jXFlly5bnz+bAhQPw7i4ahYlJ/juGW+bb+owuv9PVeWnqQ4kRUOQiKd7u4GQ4toi5j1RvW4Oxbr6U5aPzz2g22d8HelcoTs+/f0PXx2R+oO93VJchV+Hvu/jOiOXjd5yn0rl+UV1IzWIDmaBbXiEF+jnF1frSoT1ycZOvqS6lwBHVyxRzbRtMbq+lC8Ks0Y4Axwzf9HihJTWtkNpe0ccn0A+pvoKmXhdUscJ6joaNwGK8i4+7+kL1IiuJ8G/xhMcLq1pROAAr1sfqGtweRcrccPHn/4Alfy1q/jlrQW5G6jugUz+pLsZWm92PaCXbcsvFF9fN6gY9cWHD3l0tSkEupP+yjbewKp4htM1ztKdvdHkvSbepflA95tTpw+dgnIghF7IPuW5bZWLuuotv/UOq91R3NhVTgGmbhmSL8odA/LrqMXo1Pa8hrDAd/vvwVnBTONalCBqDMdobyl1RcwqzuUg/3XeZ2RzT7cgmhnAcJUWtYBdzw+NVpBFai6a1jBOnTFxw+2zWrgaze5rNrZFmDV9yl0uIzrHQoLre0JfUhDSlMsLqsPTWKae8Rm7r/pvQxi1/ACiJOnuuG1veAAAAAElFTkSuQmCC>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABkAAAAXCAYAAAD+4+QTAAACS0lEQVR4XpVUT4iPURS9tzTIrNRIymwUkyJrsbFRYydiM7OQssZYWFA2JJHFNEnKbzXSlGxMjLEyNTsWUyglGymLaTZIFpx777vv3/e+iVPnvfvOPe+++97vmyFycDVH5ILEHUMCe7bpidlS64oF2tlWLQenjITc5+yR/xONG6jkWnfubUiQNZ+gWitRoWFpSJSaZhrB+Ab8Da7Gc1q7gtbuJbtTnqt8X8F5S3QqtAs4Mi33WRlXmA5g/IPgvHscRVNVh7qOhVqnR2hyiuQQpj1JKpH/wHXazjGHjrUh4AX4oSc7jo2zmF+Bb8EzwTcEDsB34A1ow5jvg0/A17BcDp3pqVsQ/ARvy06D5jZheIxwCfHWkJD5S3CcxXSc9FB5avk9eUfwnWbT9nrf4whEOFrelO9h+A5uD8I28Bx4K6ylY2nkLvgD3BV0gE+QHxJwh63Yxugh/ax/4cRvmK/huW+y3fQI158e4wmZn+UCDA8QfIoCsALOh8fz8RBZJxczX0JajqCk+KZUMn0zuIbFdV1BGyUrdgHcCUW+MoFcXfTJ4mgbD6c1nRQf4n22VEyIBo7BtRszHwyCzFfBU2pjljdZRvQQ3GB7te4V8FFYy8PMUHyWeL1p8L2teSCCFBBxEYXnpLo7gf0o8hHzZ3ABfE7ehIPpKcZLhYZ9SLwk+zCOpbM56yM/Jqy1J42rZFj6H2CdVjRFgVVsaM1FRFtdB74h3xhj/RcSr9FjytDSHL3/rzqbOkKF3nx5QGy411/BfaX/X3fTOlbu5P4CGQFIsZUfCb8AAAAASUVORK5CYII=>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAF4AAAAXCAYAAACChfjKAAAFAklEQVR4Xr1YeehmUxh+DxrLWDO28Mc0dtmyLzUZpGwTKf+IRLKOkjJjSaNR8gelLEn2EFHIlmXmN8iMJEVKUpOEoohQ/hnPc95z7j33LPee77vfb556fvc7z/u877n33Hvf73w/EQfjP9QgNsfjAiptZZQKDOmlONETS0KJMCGS/ESQjJYIDiU9h8BrJsuMYXObAmMqVcLM5xwzrK2lhla3EMzIrZQJFtGdP8wsVylHhjB9poVPH1mmBhNNUWGusFjU+hqEdy+X3L3BI6GV7N/ZFZVssYxUi8lTw4zJs7so5DdyIT6ImrwaTz1OBb8FN4PvOe10TPK90172xhDpQ5gIM8Is64aPtK9rhqboj04NPZdFoou8OtCPcNqqRithnk5NweLDE5gKTxlVuUOm8BSGvA0uFV3kMwJthdOODTSJH5j0yR+Hicol5kTIoMaTmIJxHKpCmuSU58F/we2D0GvgpmBcwu7gm6I36S9wI2reieOCjoswshX+3hYKvfDhAds02EH0Vf4I/FT0KXsDvDDwnAg+A24Aj3fa/uB34E3e5LA1eAP4tKifT/Ln4FGBZxfwcfBncA68G/wdfDXwbAv+DT6qw94rfxhh1DMn4/M24FK4n8XxC/CYrlVuBK/rSmntRklDM8F24HrwLXAn0WmeEn1yTnOe/US/8BaCnwkvSE9mD/AncJ3zEbyJH4rWIBbA+zrKst7eTmOdj6Wdk+BNoOdqNybYcqgtL/WSQH0xq4pcCf4Kvg8+KPog8EbzphaRn222uE/04g4OtNtFX3l/cnwtzwSXiHpvdjpxLfhYMH4I/APkF6W/gCfAbxqHyAOSzGlWGdUWt5rcC/4nejMTRItztNcyi7YzeLlo6zkLBr4ReWSSBzFFziKjC7y+zbbHd8APGleLNaKLs2+g8YKucZ8PFY271tDgR5R90n3mU08Pn7oQb2PmryON7cltLdOrSxXbQujnd8UVkuvvLc6NhUFkJsxqFeDkXAS7VXM12HrQV83qxuWA+Fc4rI1ktgu2ImKFsfXM+U3UyOFCzTQt5Gw77m4PdxSd8/5A21MaX/fqCtd6kWg/v8Voi7pH9DvLt0uFJi/BnmtNoY71FGNjELRLv/Dt9s3IBYF2Ani9i7AvU7/LjQm2Cv8kE/TSc2Cg+e0gbwDh5jThltH38nOknfMypx0Hnifa6lI012L4lC+MFuwA8DnRN2CZ0RvMdjkHHhIaxyGateeu+dCu4J/gxW68F/il6AVzx8JdzGIXI34R7eHEbuBL7uhxJCozd6mb4iThF5uxOxePeM7DwB/AzcjYR9o5V2L8j3tM2Pp4Pn24NRYCLBf9VYx68i54ilV7FsjCx7O+jGiljF7AMpjZF3lx3BnwCeNCrBPtkyF4AdwhbED5R8R9oUXgLmIj+InoInJP/ULHYTin7cVzottWzGk4J3Y/zZxsXxyvBVc6bXpwPXoXsignuo5jtYx6Z4CapB7PQaJvz1Wt1OP2iCz9Gf3RaTFYdcAwEHaocw2Bvxzxo8Tw6GC4y+Dr7ffvs0d87vE4ROG3wDiUa2YjWXEQzCpm3iHapy9xY/b+TdLZ8xdzFZ1wj9eHQkv02Q57SigGDRZ5V1fVUd5JlCMWA+EGWR+/SH8T7d2viP4bd2AnEiHRE2ELITNvnRTARbuHPvRbbDSxJMKEyJ3d2Jqzw8RnMnHCGEw9WX9if3QLYB5O4H9TGbI9WENdyAAAAABJRU5ErkJggg==>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIwAAAAZCAYAAADja8bOAAAFKUlEQVR4Xt2aW+hnUxTH1xlGyX0SpTyMhgjxgFISSkkyotwpTHmgZkp5lbx4QCLKbXJPDcolRDRKuUWklKIplxjkNnmZeZhZ6+xz2XudtdZe+/zO+f+MT63//3e+67LXPmf/zu3/B+BUXChnghIdU9ZaDKsTywdZd0pRcATP49s2ueicfzRiYVHcOymaCgUbCZJL0mRxZuwxE+9qtBfRjo7FlD7erkvkIzTGZ06Pvxd/ZMLINA/Tl04rPoR2Se9Inbi1NhFEnC0qYYpcw31828WopImYdey++KzDRFyN9jIXkYPQzkF7HO3P1DVkpZqtKRrMH5yLzPn/T2hzXYX2E9oFtBEFnYq2He15tK/R/updY9FasDxwFdr3aLvR7ma+BKMG8SQXnNwDYe40/oXMF5EZ3UldxSwVnGbIzFyM9i1QD3oXr0GyYNpAPSFlTFySQz3SAbsoFt2EUm8xtQRaNLvQDuMON2wXePfIMtF6fAbtwXZDCWILZsW5F8L4+3GHjDiLt7lQwCdob3Ixw6WgNNJAZ6vVdsgUeOp7Ynq+Qbs1lQYFlr1gvsSWXuKizKD3lnfiDTUqoY46AsLZbVOi5qF9ehcXG25DewTcpUqZqSxyCISdsT4zRrJg7NDJocd86pEe+T9C+wLtPbQ1cZCDZMFk6Sd5LYTxn0D7GG0b2sNJhM59aDcy7TwI+3OfXvKU8sRMjDDkKWi7UT+bOxj5M4xQvAy1wE0QDthzEBY48SHa012Ej7IF01E9BWEf3Q7hIB+K2k78vSGNE6EHCnpouKaZ35kQ+ji4DVBnvQzqZoSOIul0CAfj5F4SoQXzdywIZSM0r6ab0D3Wd0yjfn6kD0LFByDMiQ5y/TtjW0OaUCsIP6BtZuoO/PHsMEFkX7QX0O7A1Heh4MbZV17Hyrd8FvUZpv5tV2ALxgw+C8K3KFgVfe6saj+/gXagUY8cdMAeYzo9Zn/OtAixnnGGieOT3OMh7J/rI+3YWqvg/kjLcS7ab2gbucONOCWGJ2Y0oXh7f1BfkozxaMH8w8XJGR63EyD0d2XkOa7RHo00D+KCMeZM3Az1WNVRkUaXIhr/ukgLyMXoC/Qp2uEQLqv0ktSBXKxDc2t6jCdG4QAIk1ffbzS1acHsSBwZFugphi6V1N9JkXYn2r9ox0SaB3HBdMgN34L2M9O2on0Fvkd8umehp9C2V7oHoktsv2jkcZeAv5FtkD9V0s6mg0QLTC+ddaQBajgRnKuq8Baa3mkQZ0A409E3n2FWI+wFw2iqnYhGN7hHNjItoN8h9KFCuWinQVgs8WIn6J7mFbQrWiHb+cL4RhhGDRVic0U3cEPWoP4+hL8htTeIf0C4J6HTrAs+JN92QPcR9FREZznqp/4TRgnNK+xmwXg76OIuQ/sM7dVm7uu6EJP6Bld7mMD7NvgA+qe+yfDOzkVTjNWsbsAfv0L494ZG6j6NprxEnCFlS1oRRWeY0TjaTEIc8RQjh5WoAcunwXPoncAvaJczfRC4kswwNl0iJmSxDu1s22viTO3CnPHAIuna/Hos7K345w9ysKT915mpZ6ssvZGk/4c5nzuWR9yu1foMqF8/vu3Bk8Nj+DZThm6FNNCdlqMptD9+2IK/43cOMzKm/cIdYAQYLsh5iXyEg9FFRic6aevPMM40JZsq7mJCoCDNj39Qf2TDIGEgTEulj6Dp8+BaC0PvUHFSlKgHk0f35pFyJW3F8Tbhjespy7CjI2/7UUgQpA7LV8601WZDbVN1LI5Seg+RWaZm7jYi0QAAAABJRU5ErkJggg==>

[image18]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACsAAAAXCAYAAACS5bYWAAADk0lEQVR4XpVXW4hOURReO2VcQ+7hQULI5WFcihKjlHFJKS8i0eSuPLmVyIM88CSSXAsRZaaYmjDjkkseFClJTZJRFNFQXsa39lp7n33O3mf+f75859/7W99ea9/OmRAlYYpC1chGcqsHebqzmiicJfeB0JFwd9d3KNMZuWqVjWEjFJxo3D8wMqZhbXlvJIUlKqLMGGUth7dWsGfhapZb5lDdh9EwOW9hoE4snS5LFsdjpecoy1GiOzkVTmkONhYZEhshmI/Oe/x24bdFtUXgR/S7vKsUYd7UzkWziRwxurcPIztZOhxo060m3niElQqT8+2CPesm8oRIhBNXbx3JZOuCAbuslhjvURaTAsUpJtwJqQpcBf+CfYMEd8D2MGE/cB/4GHxGspomxFd7B9Fc8DL4HJyt2jjwAxLt9i5BL3AH9Eskft6xV+DMwDMIPAd2gG3gEfAHeDvw1GAOneAZJ/QBH4F3wYHESzB00chxLLBbacxYPPnS9wdfgld07HDwC9iqfQYv/AF40fYM9cazEexCjlHq4TxPKKvJ4InzcTcEp1VnNaJV6qHjKkx2AnCA5DhqtL8fXAJOIPHuUZ2xFTwrTVvgFPiT5GVxOA++C/onYS3W5JNlbXygHQP/kWyATciT4p0VcD1DzXjeT1y7oyQJx3BH4xvALRqfInHjj00OynxG44IKvLucg49eHRb30HrrNAWujv+MUT3J1vOqSBLba9FJ+c+HwNAb8GFB5aMcq215c4lWBK/6NNUatL9U+1rTYgBJzRNeMTSCCr56exzG3g2HlSQm1uaA21Xne8b37pDfC4NjNH7HWGAvj52YaX4BPGkeKRsk+R3q7DyIllFWc736ahFbzqbB4C9wjQ4aCb5WE7/p/PYHd8h8JbmTjCHgDf11mKGLX6j9eeA3sMMuT9ZYrDkV/ERSczRlNfeCf3BCPKrZndRikjcd99RcJ16JDG4FN1qHhTXzW8nF+XN0GpyVxR3MJjxewP6UpPBv8FrOkdVsw8VrglJrpGYj+q4mXy3+ivC144lXCX/9ok4OccRMItmxzYlghvyfsgTCeCVvdRiKPNvsb4adxEeZfV97DpOcnkqJSB6p0VY4SLKLa1UbArmd7De5OCZKIKjG41EpzijWzXr8Mn3HkbZAuoX2TfzyH5LQk0eJ7FAhnEY4KE4QK9VBxoXPfKtMiBA4cub8f09sO5ksKVJSZykhWwT6f/C1lAaZcLrSAAAAAElFTkSuQmCC>