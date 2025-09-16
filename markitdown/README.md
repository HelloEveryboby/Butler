MarkItDown is a lightweight Python utility for converting various files to Markdown for use with LLMs and related text analysis pipelines. To this end, it is most comparable to textract, but with a focus on preserving important document structure and content as Markdown (including: headings, lists, tables, links, etc.) While the output is often reasonably presentable and human-friendly, it is meant to be consumed by text analysis tools -- and may not be the best option for high-fidelity document conversions for human consumption.

MarkItDown currently supports the conversion from:

* PDF
* PowerPoint
* Word
* Excel
* Images (EXIF metadata and OCR)
* HTML
* Text-based formats (CSV, JSON, XML)
* ZIP files (iterates over contents)
* EPubs
