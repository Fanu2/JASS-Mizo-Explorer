<img width="1737" height="1007" alt="image" src="https://github.com/user-attachments/assets/fe957f8b-d0e9-4510-812d-044fc56fb631" />

# JASS Multilingual Explorer v0.3.2 --- Mizo Parallel Edition

A lightweight desktop explorer for browsing and searching English--Mizo
parallel text.

This edition extends the JASS Multilingual Explorer with a dedicated
**Mizo--English Parallel 20K** database while preserving the read-only
corpus workflow and the existing Mizo Romantic Studio features.

## Highlights

-   **20,000 English ↔ Mizo parallel sentence pairs**
-   Fast Mizo and English searching
-   FTS5 full-text search support
-   Contains-search workflow
-   Search-result highlighting
-   English ↔ Mizo language selection
-   Result navigation
-   Mizo character and word counts
-   English translation display
-   Read-only database access
-   Romantic vocabulary search support
-   Romantic card creation support
-   Lightweight SQLite database
-   No GPU or large AI model required

## Included Database

The primary parallel database is:

``` text
Mizo_English_Parallel_20K.db
```

Database contents:

``` text
corpus_metadata
mizo_parallel
mizo_parallel_fts
mizo_parallel_fts_config
mizo_parallel_fts_data
mizo_parallel_fts_docsize
mizo_parallel_fts_idx
```

The main table is:

``` text
mizo_parallel
├── id
├── english
└── mizo
```

The database contains **20,000 records**.

## Source Dataset

The database was created from:

``` text
hillbyte/mizo-english-parallel-20k
```

The downloaded source contains:

``` text
data/train-00000-of-00001.parquet
```

with the columns:

``` text
en
mz
```

Source validation performed before database integration:

-   20,000 rows
-   0 empty English entries
-   0 empty Mizo entries
-   0 duplicate English--Mizo pairs
-   0 duplicate English entries
-   0 duplicate Mizo entries

Average source length:

-   English: approximately 104 characters
-   Mizo: approximately 108 characters

## Why This Project Exists

Mizo is a relatively low-resource language. Instead of depending on a
large Mizo-specific language model, this project provides a practical
way to **explore real Mizo--English language data directly**.

The Explorer is intended for:

-   language learning
-   vocabulary discovery
-   translation study
-   sentence comparison
-   corpus exploration
-   Mizo writing research
-   linguistic experimentation
-   discovering examples of Mizo usage

The application works with ordinary SQLite data and therefore does not
require a GPU.

## Example Search

A search for:

``` text
hmangaihna
```

returns many Mizo sentences containing the word.

For example:

``` text
Pathian anpuia siam kan nih angin, kan nunah Pathian
hmangaihna chu kan lantîr thei a ni.
```

with its corresponding English translation:

``` text
As we are created in God's image, we have the ability
to mirror God's love in our lives.
```

The Explorer can highlight the matching search term inside the displayed
Mizo sentence.

## Application

Main application:

``` text
JASS_Multilingual_Explorer_v0.3.2_Parallel_FIXED.py
```

The application is designed to remain lightweight and can be used
without:

-   GPU
-   PyTorch
-   CUDA
-   Ollama
-   a local LLM

The parallel corpus itself is simply searched from SQLite.

## Running

From PowerShell:

``` powershell
py .\JASS_Multilingual_Explorer_v0.3.2_Parallel_FIXED.py
```

Make sure the application can access:

``` text
Mizo_English_Parallel_20K.db
```

The database is opened in **read-only mode** by the Explorer.

## Architecture

The important design principle is to keep the existing Explorer UI
independent from the physical database schema.

The parallel database adapter normalizes:

``` text
id
english
mizo
```

into the common Explorer result structure:

``` text
id
text
english
source_line
character_count
word_count
```

This allows the existing result viewer, highlighting, navigation, and
statistics components to work without modifying the underlying corpus.

## Search

The parallel corpus uses SQLite FTS5.

Search capabilities include:

``` text
Mizo
English
Both
```

and the Explorer supports the existing search modes such as:

``` text
Contains
```

The FTS5 index provides a scalable search path for the 20,000-pair
corpus.

## Current Status

### v0.3.2 Parallel FIXED

**Status: Working / validated**

Verified:

-   Database opens successfully
-   20,000 parallel pairs available
-   Mizo search works
-   English search works
-   FTS5 index is populated
-   Search results display correctly
-   Mizo text displays correctly
-   English translation displays correctly
-   Search highlighting works
-   Character counts work
-   Word counts work
-   Result navigation works
-   Read-only database workflow is preserved
-   Romantic Studio functionality remains available

## Project Philosophy

The Mizo Explorer follows a simple principle:

> **Data first, lightweight tools second, AI optional.**

For low-resource languages, a high-quality searchable corpus can be
useful even when a capable language model is unavailable.

The project therefore focuses on making Mizo language data:

-   searchable
-   readable
-   comparable
-   reusable
-   easy to explore

## Future Data Expansion

The current 20K parallel corpus is intended to be a foundation rather
than the final Mizo collection.

Possible future additions include:

``` text
Mizo monolingual corpora
English–Mizo translation corpora
Mizo songs and folk tales
Modern conversational Mizo
Mizo educational material
Mizo speech/audio datasets
```

Future datasets should preferably be integrated as separate databases or
adapters rather than changing the stable Explorer core unnecessarily.

## Stability

The working parallel-corpus integration should be treated as a stable
checkpoint.

Future development should prioritize:

1.  adding useful Mizo datasets
2.  preserving the existing UI
3.  avoiding regressions
4.  keeping corpus databases read-only
5.  maintaining a common adapter interface

## Requirements

Typical requirements:

-   Python 3.14+
-   PySide6
-   SQLite (included with Python)

No GPU is required.

No PyTorch installation is required.

No large language model is required.

## License and Dataset Attribution

The application code and the source dataset have separate licensing
considerations.

Before redistributing the database, verify and preserve the license and
attribution requirements of the original:

``` text
hillbyte/mizo-english-parallel-20k
```

Do not assume that the application license automatically covers the
dataset.

## Credits

**JASS Multilingual Explorer**

Mizo Parallel Edition

Built as a lightweight corpus-exploration tool for English--Mizo
language data.

------------------------------------------------------------------------

**Current milestone: Mizo English Parallel 20K --- Working**
