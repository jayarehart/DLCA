# Legacy code

This directory holds research code that was removed from the `DLCA` package during cleanup (issue #9).

- `carbonation/` contains `Carbonation.py` and `carb_models.py`, a carbonation model that the pipeline never called.

Status:

- This code is kept only as a reference for porting in milestone M3.
- It is not part of the `DLCA` package and is not tested.
- It is not expected to import or run as-is.

The full pre-cleanup state, including the removed `DLCA_archive.py` and the DOE HTML scrapers, is tagged `legacy-2023` (commit `5b460de`). Use `git show legacy-2023:<path>` to view any removed file.
