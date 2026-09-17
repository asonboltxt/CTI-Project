# Exact-format CTI proposal reader update

This parser is specialized for the table and checkbox structures used by the V4.1 proposal templates and the V4.5 mock prioritization test packages.

## Apply
1. Stop Flask.
2. Back up the CTI_V482 folder.
3. Copy document_reader.py and proposal_parser.py to the project root and replace existing files.
4. Replace templates/review.html.
5. Append style_addition.css to static/style.css.
6. Run `python -m pip install -r requirements.txt`.
7. Run `python -m py_compile document_reader.py proposal_parser.py app.py`.
8. Start with `python app.py`.

DOCX uses exact table locations and checkbox glyphs. PDF uses layout-preserving extraction and the same exact labels. Scanned PDFs still require OCR.
