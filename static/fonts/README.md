# OpenDyslexic Font

This directory is intended for locally-hosted OpenDyslexic font files.

OpenDyslexic is a free, open-source typeface designed to increase readability
for readers with dyslexia. It is licensed under the SIL Open Font License.

## How to add local font files

1. Download OpenDyslexic from https://opendyslexic.org/
2. Place the .woff2 and .woff files in this directory:
   - OpenDyslexic-Regular.woff2
   - OpenDyslexic-Regular.woff
   - OpenDyslexic-Bold.woff2
   - OpenDyslexic-Bold.woff

The CSS in `static/css/accessibility.css` will automatically use local files
if present, falling back to the CDN if not found.

## License

OpenDyslexic is licensed under the SIL Open Font License, Version 1.1.
See https://opendyslexic.org/ for details.
