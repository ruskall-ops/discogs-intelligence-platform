# Discogs Intelligence Platform v3

This is the first database-backed desktop version.

## What changes in v3

- `discogs_intelligence.db` is the permanent source of truth.
- Collection records, historical market snapshots, scores, decisions and notes
  survive between runs.
- Excel is now an export, not the database.
- You can search your collection, filter it and double-click a release to save:
  - Keep / List for sale / Maybe / Ignore
  - Would I miss it?
  - Protected from sale shortlist
  - Personal notes

## First run

1. Unzip the folder.
2. Right-click `Run Discogs Intelligence Platform.command` and choose **Open**.
3. Click **Import Collection CSV** and select your Discogs export.
4. Click **Refresh Discogs Data**.
5. Paste a valid personal access token when asked.
6. Leave the app open during the approximately 25–35 minute first refresh.

Your token is used only for that refresh and is not stored.

## Later runs

Double-click the launcher. The database and your decisions are loaded automatically.

Run a fresh market-data refresh monthly to make Momentum and Hot Now detection useful.

## Backup

Back up this file:

`discogs_intelligence.db`

It contains your collection intelligence history and personal decisions.

## Current limitations

- Current value still uses Discogs' lowest available listing, not completed-sale history.
- Discogs API rate limits mean a full refresh takes about 30 minutes.
- The app does not yet automate scheduled refreshes.
- Personal decisions from the earlier v2 workbook are not imported automatically.
