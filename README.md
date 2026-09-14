<img width="1737" height="1027" alt="image" src="https://github.com/user-attachments/assets/e22a811a-eb42-40f0-9a1e-f7757e031ac8" />

# JASS Mizo Language Explorer

## Stable Mizo Language Edition

JASS Mizo Language Explorer is a desktop application for exploring,
searching and creatively working with Mizo-language corpus content.

The project uses a large Mizo corpus as its read-only linguistic source
and provides a separate creative layer for translation, editing and
romantic/nostalgic card creation.

---

## Status

**STABLE BASELINE**

Current application:

**JASS Multilingual Explorer v0.4 — Mizo Romantic Card Studio**

The Mizo implementation is now treated as a stable version.

Future development should prefer:

- verified bug fixes
- usability improvements
- additional content
- additional themes
- additional languages
- non-destructive enhancements

The original corpus must remain unchanged.

---

## Core Principles

### 1. Corpus is Read-Only

The original Mizo corpus is never modified by the application.

### 2. Explorer and Creative Studio are Separate

Corpus exploration remains independent from the creative card-generation
workflow.

### 3. User Controls the Final Message

Machine-generated or translated text can always be edited before it is
used in a card.

### 4. Translation is Optional

Failure of an online translation service must not prevent the user from
creating or editing a card.

### 5. Preserve the Source

Corpus source lines and source information can be retained for reference.

---

# Mizo Corpus

Source file:

`mizo_language_corpus_4m.txt`

Corpus size:

**4,000,000 records**

Database:

`JASS_Mizo_Corpus.db`

The corpus database contains:

- 4,000,000 source records
- 4,000,000 FTS records
- Source line numbers
- Full-text search support

Verified source SHA-256:

`e03744a1ce462374329c8ca87d4983552d06166e58d8fddad9d4d032d5f7da9d`

Verification status:

**PASSED**

Source modification:

**NONE**

---

# Mizo Explorer

The explorer allows the user to:

- Search the Mizo corpus
- Browse matching records
- Inspect complete source text
- View source-line information
- Work with long corpus records
- Identify interesting linguistic and cultural material

The explorer operates against the read-only corpus.

---

# Romantic / Nostalgic Studio

The Mizo edition includes a dedicated Romantic Card Studio.

It is designed for turning meaningful Mizo passages into attractive
personal messages and cards.

## Editing

Users can edit:

- Card title
- Original Mizo text
- English text
- Additional romantic wording

The English text is fully editable so that the user remains in control
of the final message.

---

# Romantic Card Features

## Themes

The current studio includes:

- Rose Garden
- Midnight Romance
- Soft Love
- Classic Letter
- Lavender Dreams
- Sunset Love
- Ocean Hearts
- Golden Promise

## Text Colours

Available text colours include:

- White
- Ivory
- Rose
- Gold
- Lavender
- Black

## Text Sizes

The user can independently adjust:

- Title size
- Mizo text size
- English text size

## Card Formats

Supported formats:

- Portrait — 1080 × 1350
- Square — 1080 × 1080
- Landscape — 1350 × 1080

## Export

Cards can be exported as:

- PNG
- JPEG

---

# Romantic Message Editing

The studio supports adding additional personal wording.

Built-in quick additions include:

- With all my love ❤️
- I will always cherish you.
- Forever in my heart.

These are only starting points. The complete English message can be
edited by the user.

---

# Translation

The application can use online Mizo → English translation when available.

Translation is deliberately treated as an optional convenience rather
than a dependency.

If translation is unavailable, the user can:

1. Continue using the application.
2. Edit the English message manually.
3. Create the romantic card normally.

---

# Example

A Mizo passage can be transformed into a personal romantic message.

Example theme:

**Memories • Longing • Distance • Love**

The user can combine:

- Original Mizo passage
- English rendering
- Personal words
- Romantic theme
- Custom text size
- Custom text colour

and export the result as a shareable card.

---

# Architecture

The project has two conceptual layers.

## Language Exploration Layer

Responsible for:

- Corpus access
- Search
- Record browsing
- Source references
- Full-text retrieval

## Creative Studio Layer

Responsible for:

- Text editing
- Translation result editing
- Romantic message composition
- Visual themes
- Typography
- Card preview
- Image export

The two layers should remain loosely coupled.

---

# Stability Policy

This version is considered a **Mizo Stable Baseline**.

Do not repeatedly redesign the application.

Future changes should be limited to:

### Allowed

- Verified bug fixes
- Translation reliability improvements
- UI usability improvements
- Additional romantic themes
- Additional fonts
- Additional card layouts
- Additional export options
- Better text positioning
- Additional Mizo content
- Additional language support

### Avoid

- Rewriting the corpus database
- Changing the corpus source
- Removing working functionality
- Unnecessary architectural rewrites
- Breaking the existing card workflow
- Modifying source corpus records

---

# Planned Enhancements

Potential future improvements include:

- Drag-and-drop text positioning
- Independent positioning of Mizo and English text
- More decorative elements
- Background image support
- User-selectable fonts
- Custom image backgrounds
- Additional romantic templates
- Greeting-card categories
- Nostalgia/memory templates
- Festival and cultural templates
- Better Mizo → English translation
- Offline translation support

These are future enhancements and are **not required for the current
stable baseline**.

---

# Version

**JASS Multilingual Explorer v0.4**

Edition:

**Mizo Romantic Card Studio**

Status:

**STABLE**

---

# Philosophy

> Explore the language.  
> Preserve the words.  
> Add your own feelings.  
> Create something beautiful.

---

## License

Add the appropriate license here according to the licensing terms of
the application code and the source corpus.

The corpus license and attribution requirements must be preserved
separately from the application license.
