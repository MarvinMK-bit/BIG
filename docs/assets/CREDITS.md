# Image and font credits

Every image used in BIG's documentation and web interface, and every font BIG bundles,
is listed here with its author, source and licence. Attribution is a condition of the
licences below, not a courtesy — if you add an image or a font, add its entry here at
the same time.

Note that BIG's own name and logo are **not** covered by the Apache-2.0 licence or by
any licence below. See `NOTICE`.

---

## deep-blue-cabinet.jpg

IBM's Deep Blue — the RS/6000 SP cabinet on display at the Computer History Museum.

| | |
|---|---|
| **Author** | James the photographer ([Flickr](https://www.flickr.com/photos/jamesthephotographer/)) |
| **Source** | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Deep_Blue.jpg) |
| **Licence** | [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/) |
| **Modifications** | None |

Required attribution line, to appear wherever the image is displayed:

> Deep Blue by James the photographer, via Wikimedia Commons, [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/)

---

## DejaVu Sans (font)

`backend/app/services/annotate/fonts/DejaVuSans.ttf` and `DejaVuSans-Bold.ttf`, the
typeface of the marks, scores and footer drawn on annotated scripts. Bundled so every
deployment draws them the same way, whatever fonts its system has.

| | |
|---|---|
| **Author** | Bitstream, Inc. (Bitstream Vera); the DejaVu fonts team; Tavmjong Bah (Arev glyphs) |
| **Version** | 2.37 |
| **Source** | [dejavu-fonts.github.io](https://dejavu-fonts.github.io/) |
| **Licence** | [Bitstream Vera Fonts licence](https://dejavu-fonts.github.io/License.html), with the Arev Fonts licence for glyphs taken from Arev; DejaVu's own changes are in the public domain. Permits redistribution, including commercial use, as part of a larger work. |
| **Modifications** | None |

The licence text travels with the fonts in `backend/app/services/annotate/fonts/LICENSE`,
as the licence requires. It forbids selling the fonts on their own and requires any modified
version to be renamed; neither applies to BIG's use.

---

## Adding an image

Before adding any image to this repository, confirm three things:

1. **The licence permits commercial use and redistribution.** BIG is Apache-2.0 and
   publicly hosted. A "non-commercial" or "no derivatives" licence does not fit.
2. **The subject carries no separate rights.** A photograph can be freely licensed
   while its subject is not — museum signage, product packaging, artwork, and
   identifiable people all carry rights of their own, independent of the
   photographer's licence.
3. **The attribution is recorded here and displayed where the image appears.**
   Crediting an author is not the same as having permission; both are required.

Images taken by BIG contributors themselves are simplest: note the author and that
the work is released under Apache-2.0 along with the rest of the project.
