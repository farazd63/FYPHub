# Proposal reference specification - review draft

## Scope and evidence boundary

The approved source files are preserved outside the repository:

- `D:\FYP Project\short proposal.pdf` - 3 pages.
- `D:\FYP Project\long proposal.pdf` - 17 pages.

They are **filled reference examples**, not blank generic templates. Their people, IDs, supervisor, title, institution branding, term, project-specific prose, 12-module content, and page count are not imported as universal requirements or made available as generic downloadable templates.

### Extraction method and uncertainty

Page geometry and embedded-font resources were inspected with `pypdf`; representative rendered pages were visually reviewed with PyMuPDF at 1.5x: short pp1-3 and long pp1-3, 9-10, and 14-16. Both files use A4 media boxes (`595.276 x 841.89` points), no page rotation, and embedded Computer Modern families. This supports only an observation that the examples are A4, Computer-Modern-typeset documents. It does **not** establish official university paper, font, size, margin, spacing, or heading rules.

| Candidate rule | Source / method | Classification | Configured? | Reason |
| --- | --- | --- | --- | --- |
| Short and long are distinct document types | both PDFs, titles and content | Directly observed | No | The examples are filled documents, not blank templates. |
| A4 portrait media box | both PDFs, page dictionaries | Directly observed | No | Official page-size policy was not supplied. |
| Computer Modern embedded fonts | both PDFs, page font resources; rendered pages | Directly observed | No | An example's typesetting is not an official font rule. |
| Centered branded cover page | both PDFs p1; rendered | Directly observed | No | Branding and cover data may be project/institution-specific. |
| Serif body text; bold hierarchy and bullets | short p2; long pp3-16; rendered | Directly observed | No | Exact font, point size, spacing, indentation and heading levels remain unapproved. |
| Numeric margins, line spacing, page numbering placement | visual pages only | Ambiguous / inferred | No | No authoritative numeric specification is present. |

## Observed section order

### Short reference

| PDF page | Observed heading/order | Classification |
| --- | --- | --- |
| 1 | Cover: `Final Year Project Short Proposal`; project title; named students; supervisor; department/faculty/university/location/term | Filled cover example; personal/project content is not reusable policy. |
| 2 | `Introduction` -> `Purpose` -> `Targeted Audience` -> `Product Functions and Features` -> `Social and Industrial Impact` | Directly observed headings/order in this example only. |
| 3 | Supervisor consent form and student/supervisor fields | Supporting filled form example; not configured as a generic submission requirement. |

### Long reference

| PDF page(s) | Observed heading/order | Classification |
| --- | --- | --- |
| 1 | Cover: `Final Year Project Long Proposal`; project title and personal/institutional content | Filled cover example. |
| 2 | `Revision History` | Directly observed example section. |
| 3-4 | `1. Project Stream` -> `2. Introduction` -> `3. Project Description` -> `4. Real World Problem` -> `5. Problem Statement` -> `6. Names of Existing Similar FYPs (if repeated)` | Directly observed example order. |
| 5-8 | `7. New Functionalities (main) to be added Features` -> `8. Application Review` and numbered review subsections -> comparison table | Directly observed example order; its products/modules are not generic required content. |
| 8-14 | `9. Scope`, `9.1 Included Aspects`, `9.2 Excluded Aspects`, `9.3 Modules Description`, then module sections; `10. Modules` and allocation table | Directly observed example order; the 12-module content is project-specific. |
| 15-16 | `11. Development Environment` -> `12. Significance` -> `13. Tools and Techniques` | Directly observed example order. |
| 17 | `References` | Directly observed example section. |

## Safe M1-D seed data boundary

M1-D may create administrator-managed **metadata and academic-rule versions** describing a future short or long template. It must not import source PDF bytes, personal data, title/topic text, institution logo, or project-specific body content. Uncertain candidate rules remain absent/unconfigured until a designated academic authority confirms them.

## Pending authority decisions

1. Which observed headings are mandatory for each template type, and which are optional or project-specific?
2. What are the official numeric formatting rules and their source document?
3. Which authority approves, activates, retires, and retains template/rule versions?
4. What storage and role-based download policy applies to official blank template files?
