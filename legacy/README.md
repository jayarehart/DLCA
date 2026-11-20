# Legacy code

This directory holds research code that was removed from the `DLCA` package during cleanup (issue #9).

- `carbonation/` (`Carbonation.py` and `carb_models.py`), a carbonation model that the pipeline never called, was deleted in #74. It was not ported: M3 implements Lagerblad (2005) instead, in `src/dlca/inventory/carbonation.py` (decision record 0017). Issue #74 lists the bugs found by reading it. To see the old code, run `git show v0.3.0:legacy/carbonation/Carbonation.py` (and `carb_models.py`).

The biogenic regrowth uptake (a Cherubini et al. 2011 Gaussian in `EmissionsFluxEngine.create_flux_mat` and `EmissionInventoryBio`) was removed in #61 and is not kept here. M3 rewrites it. To see the old code, run `git show v0.2.0:src/dlca/engine.py` and `git show v0.2.0:src/dlca/models.py`.

Status:

- Nothing is left here to port. The directory is kept for this note.
- It is not part of the `DLCA` package and is not tested.
- It is not expected to import or run as-is.

The full pre-cleanup state, including the removed `DLCA_archive.py` and the DOE HTML scrapers, is tagged `legacy-2023` (commit `5b460de`). Use `git show legacy-2023:<path>` to view any removed file.
