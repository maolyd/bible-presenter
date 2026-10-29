# Bible data folder

This folder holds Bible **source files**, separate from the program code.

* `bibles/` – complete public-domain Bibles offered by *Bible library → Install bundled Bibles*:
  * `eng-kjv.osis.xml` – King James Version (English, default)
  * `fra-lsg1910.beblia.xml` – Louis Segond 1910 (French, default)
  * `eng-web.usfx.xml` – World English Bible (English, optional)
  * `catalog.json` – name, code, language, licence, source and SHA-256 checksum for each file.
    To bundle another *legally distributable* Bible, copy its file here and add an entry.
* `sample/` – **SAMPLE ONLY** files with a handful of verses, for trying the import screen. They are not complete Bibles and are marked *partial* if imported.

The program never reads text directly from here during a service: importing copies the text into
`%LOCALAPPDATA%\BiblePresenter\bibles.sqlite`. Details and licences: `docs/BIBLE_DATA.md`, `LICENSES.md`.
