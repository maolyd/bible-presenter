# Automated test results

These are the actual results of running the test suite, not expectations.

* **Date:** 2026-10-29
* **Where:** Linux cloud container (Python 3.13, PySide6 6.8.1 with Qt WebEngine in offscreen mode, Chromium 153 via Playwright 1.48). **Not yet run on Windows** — run `python -m pytest -v` there (see INSTALL_WINDOWS.md, Step 12) and compare.
* **Command:** `python -m pytest -v` (with `BIBLE_TEST_CHROMIUM` pointing at the installed Chromium for the browser tests)
* **Result:** `128 passed in 31.34s` — the suite was run twice in a row with the same result.

| Test file | What it covers | Result |
|---|---|---|
| `tests/test_full_bibles.py` | Complete bundled KJV/LSG/WEB: counts, chapter counts, known verses, KJV-LSG exact alignment, WEB variants, search, navigation, pagination | 9/9 passed |
| `tests/test_importers.py` | Import formats (USFX, OSIS, Zefania, Beblia, VPL, zip); validation; damaged/unknown files; no external XML entities | 11/11 passed |
| `tests/test_passage.py` | Resolving ranges/chapters; validation messages; previous/next verse & chapter across books; missing-verse alignment | 10/10 passed |
| `tests/test_presentation.py` | Preview/live separation; black screen & restore; clear; live paging; one-verse-at-a-time; style persistence & validation; hidden language; default one verse at a time in a footer | 14/14 passed |
| `tests/test_reference.py` | Reference parsing; English/French book names and abbreviations; invalid references | 48/48 passed |
| `tests/test_repository.py` | Bible storage; duplicate detection & replace; failed import keeps existing data; search (accents, phrases, fallback); migrations | 7/7 passed |
| `tests/test_server.py` | Server start/stop; 127.0.0.1 only; read-only & Host checks; path traversal; SSE synchronisation; reconnect; port conflicts; offline page | 10/10 passed |
| `tests/test_settings.py` | Settings/theme persistence across restarts; favourites; recent history; one-time upgrade of saved settings to footer + one verse | 5/5 passed |
| `tests/test_ui.py` | Real operator window (offscreen): lookup→preview without changing live; errors; black/restore buttons; navigation; search; favourites; appearance | 6/6 passed |
| `tests/test_web_render.py` | Real Chromium: footer display (bottom band, transparent above, black hides band); live updates at 1920×1080, 1280×720, 854×480, 800×600; both layouts; black/restore; no controls/scrollbars; reconnect after server restart | 8/8 passed |

## Defects found by testing and fixed before this run

1. **OBS page could show an old slide** if a slow fallback poll reply arrived after a newer live update (seen in the browser tests). States now carry a version and a per-run server ID; the page never goes backwards.
2. **OSIS “milestone” verses were dropped** (`<verse sID/>…<verse eID/>`), which made the KJV file import zero verses. Fixed and covered by tests.
3. **“(none — hide this language)” did not hide the language** – the app fell back to the first Bible of that language. Now stored explicitly.
4. **Confusing error messages** for an empty reference and for “3:16” without a book name.
5. **Psalm 23 was split over two slides** although it fits on one; automatic pagination was retuned (measured: every tested passage fits with text scaled no smaller than 62 %).
6. Psalm references read “Psalms 23” → now “Psalm 23” / “Psaume 23”.
7. Verse numbers wrapped in the centre text, and chapter numbers ≥ 20 were shown as “…” in the chapter grid.
8. Footer display: the page's `<html>` element still painted the background colour, so the area above the footer was not transparent in OBS.
9. Footer display: the operator preview drew the band at the wrong size after the preview widget was resized (hidden before by the full-screen background). The page now rescales on every update and whenever its size changes.

## Windows (GitHub Actions, windows-2022, Python 3.12)

The whole suite also runs on Windows for every change (`.github/workflows/build-windows.yml`). Release **v1.0.0** was built by a run in which all tests passed on Windows, the built `BiblePresenter.exe` started, served the OBS page and installed all three Bibles on first start, and `BiblePresenter-Setup-1.0.0.exe` installed and uninstalled silently. The first Windows run found one defect: Git on Windows changed the Bible files' line endings, so they failed their checksum. Fixed with `.gitattributes`.

## Packaging check (Linux)

`BiblePresenter.spec` was built with PyInstaller 6.11.1 **on Linux**; the resulting bundle started from another folder, created its user data, and served the OBS page from its bundled files. The **Windows** `.exe` has not been built or tested yet — build it with `scripts/build_windows.ps1` and run the [manual OBS checklist](OBS_TEST_CHECKLIST.md).

## Full list

```
PASSED  tests/test_full_bibles.py::test_both_bibles_are_complete
PASSED  tests/test_full_bibles.py::test_chapter_counts_match_book_table
PASSED  tests/test_full_bibles.py::test_known_verses
PASSED  tests/test_full_bibles.py::test_kjv_and_lsg_align_verse_for_verse
PASSED  tests/test_full_bibles.py::test_web_and_lsg_differences_are_only_known_variants
PASSED  tests/test_full_bibles.py::test_psalm_23_is_paired_by_verse_number
PASSED  tests/test_full_bibles.py::test_search_full_bible
PASSED  tests/test_full_bibles.py::test_navigation_across_books
PASSED  tests/test_full_bibles.py::test_long_passages_are_paginated
PASSED  tests/test_importers.py::test_usfx_reader
PASSED  tests/test_importers.py::test_beblia_reader
PASSED  tests/test_importers.py::test_osis_reader_milestones_and_containers
PASSED  tests/test_importers.py::test_zefania_reader
PASSED  tests/test_importers.py::test_vpl_reader_reports_duplicates_and_unknown_books
PASSED  tests/test_importers.py::test_zip_container
PASSED  tests/test_importers.py::test_damaged_xml_is_rejected
PASSED  tests/test_importers.py::test_unknown_xml_is_rejected
PASSED  tests/test_importers.py::test_random_bytes_are_rejected
PASSED  tests/test_importers.py::test_missing_file
PASSED  tests/test_importers.py::test_external_entities_are_not_loaded
PASSED  tests/test_passage.py::test_resolve_single_range_chapter
PASSED  tests/test_passage.py::test_resolve_errors[John 25:1-chapter 25 does not exist]
PASSED  tests/test_passage.py::test_resolve_errors[John 3:40-verse 40 does not exist]
PASSED  tests/test_passage.py::test_resolve_errors[John 3:16-40-verse 40 does not exist]
PASSED  tests/test_passage.py::test_resolve_errors[Exodus 1:1-not in the selected translation]
PASSED  tests/test_passage.py::test_resolve_without_translation
PASSED  tests/test_passage.py::test_next_and_previous_verse_cross_chapter_and_book
PASSED  tests/test_passage.py::test_next_and_previous_chapter
PASSED  tests/test_passage.py::test_alignment_marks_verse_missing_in_one_translation
PASSED  tests/test_passage.py::test_references_in_both_languages
PASSED  tests/test_presentation.py::test_preview_never_changes_live
PASSED  tests/test_presentation.py::test_go_live_publishes_to_output
PASSED  tests/test_presentation.py::test_bilingual_slide_contents_and_missing_marker
PASSED  tests/test_presentation.py::test_black_screen_keeps_and_restores_live_passage
PASSED  tests/test_presentation.py::test_clear_then_restore
PASSED  tests/test_presentation.py::test_restore_with_nothing_live
PASSED  tests/test_presentation.py::test_next_and_previous_live
PASSED  tests/test_presentation.py::test_one_verse_per_slide_pages_then_moves_on
PASSED  tests/test_presentation.py::test_next_live_while_black_stays_black
PASSED  tests/test_presentation.py::test_style_changes_apply_to_live_and_persist
PASSED  tests/test_presentation.py::test_sanitize_style_rejects_bad_values
PASSED  tests/test_presentation.py::test_default_is_one_verse_at_a_time_in_a_footer
PASSED  tests/test_presentation.py::test_footer_settings_are_validated
PASSED  tests/test_presentation.py::test_translation_hidden_gives_single_column
PASSED  tests/test_reference.py::test_valid_references[John 3:16-expected0]
PASSED  tests/test_reference.py::test_valid_references[Jean 3:16-expected1]
PASSED  tests/test_reference.py::test_valid_references[Jean 3.16-expected2]
PASSED  tests/test_reference.py::test_valid_references[Jean 3,16-expected3]
PASSED  tests/test_reference.py::test_valid_references[jn 3:16-expected4]
PASSED  tests/test_reference.py::test_valid_references[  JOHN   3 : 16 -expected5]
PASSED  tests/test_reference.py::test_valid_references[John 3:16-18-expected6]
PASSED  tests/test_reference.py::test_valid_references[John 3:16\u201318-expected7]
PASSED  tests/test_reference.py::test_valid_references[Jean 3.16-18-expected8]
PASSED  tests/test_reference.py::test_valid_references[John 3:16-4:2-expected9]
PASSED  tests/test_reference.py::test_valid_references[John 3-expected10]
PASSED  tests/test_reference.py::test_valid_references[Psalm 23-expected11]
PASSED  tests/test_reference.py::test_valid_references[Psaume 23-expected12]
PASSED  tests/test_reference.py::test_valid_references[Psaumes 23:1-expected13]
PASSED  tests/test_reference.py::test_valid_references[Ps 23-24-expected14]
PASSED  tests/test_reference.py::test_valid_references[1 John 1:9-expected15]
PASSED  tests/test_reference.py::test_valid_references[1re Jean 1.9-expected16]
PASSED  tests/test_reference.py::test_valid_references[1 Jean 1:9-expected17]
PASSED  tests/test_reference.py::test_valid_references[I John 1:9-expected18]
PASSED  tests/test_reference.py::test_valid_references[First John 1:9-expected19]
PASSED  tests/test_reference.py::test_valid_references[2nd Kings 5:1-expected20]
PASSED  tests/test_reference.py::test_valid_references[2 Rois 5:1-expected21]
PASSED  tests/test_reference.py::test_valid_references[III John 2-expected22]
PASSED  tests/test_reference.py::test_valid_references[Jude 3-expected23]
PASSED  tests/test_reference.py::test_valid_references[Jude 3-5-expected24]
PASSED  tests/test_reference.py::test_valid_references[Phil\xe9mon 6-expected25]
PASSED  tests/test_reference.py::test_valid_references[Esa\xefe 53:5-expected26]
PASSED  tests/test_reference.py::test_valid_references[\xc9sa\xefe 53:5-expected27]
PASSED  tests/test_reference.py::test_valid_references[Isaiah 53:5-expected28]
PASSED  tests/test_reference.py::test_valid_references[Apocalypse 21:4-expected29]
PASSED  tests/test_reference.py::test_valid_references[Rev 21:4-expected30]
PASSED  tests/test_reference.py::test_valid_references[Cantique des cantiques 2:1-expected31]
PASSED  tests/test_reference.py::test_valid_references[Song of Solomon 2:1-expected32]
PASSED  tests/test_reference.py::test_valid_references[Phil 4:13-expected33]
PASSED  tests/test_reference.py::test_valid_references[Deuter 6:4-expected34]
PASSED  tests/test_reference.py::test_valid_references[Actes 2:38-expected35]
PASSED  tests/test_reference.py::test_valid_references[Jacques 1:5-expected36]
PASSED  tests/test_reference.py::test_valid_references[Matthieu 5:3-expected37]
PASSED  tests/test_reference.py::test_invalid_references[Hezekiah 1:1-not a recognised]
PASSED  tests/test_reference.py::test_invalid_references[Jo 3:16-could match several books]
PASSED  tests/test_reference.py::test_invalid_references[es 1:1-could match several books]
PASSED  tests/test_reference.py::test_invalid_references[John 3:18-16-before its start]
PASSED  tests/test_reference.py::test_invalid_references[John 0:1-start at 1]
PASSED  tests/test_reference.py::test_invalid_references[-Please type a book name]
PASSED  tests/test_reference.py::test_invalid_references[3:16-Could not understand]
PASSED  tests/test_reference.py::test_every_english_and_french_name_resolves_to_same_book
PASSED  tests/test_reference.py::test_english_and_french_references_match
PASSED  tests/test_reference.py::test_book_table_is_complete
PASSED  tests/test_repository.py::test_import_and_metadata
PASSED  tests/test_repository.py::test_duplicate_translation_detected_and_replace
PASSED  tests/test_repository.py::test_failed_import_keeps_existing_data
PASSED  tests/test_repository.py::test_search_accents_case_and_phrases
PASSED  tests/test_repository.py::test_search_fallback_without_fts
PASSED  tests/test_repository.py::test_delete_translation
PASSED  tests/test_repository.py::test_schema_survives_reopen
PASSED  tests/test_server.py::test_start_serves_page_and_assets
PASSED  tests/test_server.py::test_server_binds_to_localhost_only
PASSED  tests/test_server.py::test_go_live_is_visible_to_obs
PASSED  tests/test_server.py::test_read_only_and_host_checks
PASSED  tests/test_server.py::test_live_synchronisation_over_sse
PASSED  tests/test_server.py::test_reconnect_request_reaches_pages
PASSED  tests/test_server.py::test_port_conflict_gives_clear_error
PASSED  tests/test_server.py::test_stop_releases_port_and_closes_streams
PASSED  tests/test_server.py::test_invalid_port
PASSED  tests/test_server.py::test_presentation_page_works_offline
PASSED  tests/test_settings.py::test_values_persist_after_reopen
PASSED  tests/test_settings.py::test_theme_persists_through_app_restart
PASSED  tests/test_settings.py::test_saved_style_is_upgraded_to_one_verse_footer_once
PASSED  tests/test_settings.py::test_favourites
PASSED  tests/test_settings.py::test_recent_is_ordered_deduplicated_and_limited
PASSED  tests/test_ui.py::test_reference_lookup_updates_preview_but_not_live
PASSED  tests/test_ui.py::test_invalid_reference_shows_message
PASSED  tests/test_ui.py::test_black_and_restore_buttons
PASSED  tests/test_ui.py::test_selection_navigation_and_range
PASSED  tests/test_ui.py::test_search_and_favourites
PASSED  tests/test_ui.py::test_appearance_controls_change_output_style
PASSED  tests/test_web_render.py::test_live_updates_and_layouts_at_several_resolutions[size0]
PASSED  tests/test_web_render.py::test_live_updates_and_layouts_at_several_resolutions[size1]
PASSED  tests/test_web_render.py::test_live_updates_and_layouts_at_several_resolutions[size2]
PASSED  tests/test_web_render.py::test_live_updates_and_layouts_at_several_resolutions[size3]
PASSED  tests/test_web_render.py::test_footer_display[size0]
PASSED  tests/test_web_render.py::test_footer_display[size1]
PASSED  tests/test_web_render.py::test_output_has_no_operator_controls
PASSED  tests/test_web_render.py::test_page_reconnects_after_server_restart
```
