# V8 Inline Visual Fix

This build fixes the deployment symptom where the new HTML loaded but CSS/JS did not, leaving an unstyled page.

## Fix
- Critical CSS is embedded directly in `static/index.html`.
- Front-end JavaScript is embedded directly in `static/index.html`.
- `styles.css` and `app.js` remain as editable source copies, but the production page no longer depends on them loading separately.
- Health metadata updated to V8.

## Expected UI
- No left workflow navigation.
- Centered, minimal AI home screen.
- Large hero heading and rounded glass-style composer.
- Upload, Excel template, voice and send controls integrated in the composer.
- Quick actions are compact cards rather than technical navigation pages.
- After the first message, the interface becomes a clean chat workspace.
- Tool trace remains collapsed by default.
