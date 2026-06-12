# Generate the Appendix G Report Section (Section 3)

Runs the entire tie-down workbook and drafts the SAR Appendix G section: scope and
MIL-STD-209K basis, the full results table, and the pass/fail assessment. Every number
comes from the validated engine — the AI only drafts the prose around them.

## Inputs

- **"Workbook path"** — the MCDLL tie-down workbook. The default points at the project
  workbook; only change it to run a different file.
- **"Required SF"** — the pass threshold applied across the workbook items (default 1.5,
  the MIL-STD-209K design factor).

Click **"Generate Appendix G"**.

## Output

- A **"Preview"** expander renders the drafted section so you can read it before saving.
- **"Download .md"** and **"Download .txt"** buttons save the section as
  `Appendix_G_<timestamp>` in your chosen format for pasting into the Safety Assessment
  Report.

## Notes

- Generation runs every workbook item through the engine, so it takes noticeably longer
  than the single-item sections above.
- If the workbook path is wrong or the file is open and locked in Excel, you get an error —
  fix the path or close Excel and click again.
