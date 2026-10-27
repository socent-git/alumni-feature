/**
 * SCRIPT 1 — Extract the current Drive folder schema
 * ---------------------------------------------------
 * Reads folder names and hierarchy only. File contents are never opened.
 * Each folder also gets a count of the files directly inside it, taken from
 * Drive metadata, so empty and overloaded folders show up.
 *
 * Output (new Google Sheet, link printed in the execution log):
 *   - "Schema"   : one row per folder (ID, path, depth, counts, dates, flags)
 *   - "Tree"     : indented text tree. Copy column A and paste it to Claude.
 *   - "Mapping"  : empty mapping table that Script 2 reads
 *
 * SETUP (one time)
 *   1. script.google.com > New project > paste this file.
 *   2. Left sidebar > Services (+) > "Drive API" > Add (identifier: Drive, v3).
 *   3. Set CONFIG.ROOT_ID below. Run extractSchema(). Approve the permissions.
 */

const CONFIG = {
  // Shared drive ID (starts with 0A...) OR a folder ID.
  // SocEnt shared drive, as found on 2026-10-27:
  ROOT_ID: '0AGUWPWZlmPBEUk9PVA',

  // Add file counts per folder. Reads metadata only (parent + type), no content.
  INCLUDE_FILE_COUNTS: true,

  // 0 = no limit. Use 2 or 3 for a quick top-level view.
  MAX_DEPTH: 0,

  // Leave blank to create a new sheet. Or paste an existing spreadsheet ID.
  OUTPUT_SPREADSHEET_ID: '',
};

const FOLDER_MIME = 'application/vnd.google-apps.folder';
const SHORTCUT_MIME = 'application/vnd.google-apps.shortcut';

function extractSchema() {
  const started = Date.now();
  const isSharedDrive = CONFIG.ROOT_ID.startsWith('0A');
  const rootName = isSharedDrive
    ? Drive.Drives.get(CONFIG.ROOT_ID).name
    : Drive.Files.get(CONFIG.ROOT_ID, { supportsAllDrives: true, fields: 'name' }).name;

  // 1. Collect every folder and every item's parent (metadata only).
  const items = isSharedDrive ? listSharedDrive_(CONFIG.ROOT_ID) : listUnderFolder_(CONFIG.ROOT_ID);
  const folders = {};
  const children = {};
  const directFiles = {};
  const shortcuts = {};
  items.forEach((it) => {
    const parent = (it.parents || [])[0];
    if (it.mimeType === FOLDER_MIME) {
      folders[it.id] = it;
      (children[parent] = children[parent] || []).push(it.id);
    } else if (parent) {
      directFiles[parent] = (directFiles[parent] || 0) + 1;
      if (it.mimeType === SHORTCUT_MIME) shortcuts[parent] = (shortcuts[parent] || 0) + 1;
    }
  });

  // 2. Walk the tree depth-first, sorted A-Z, so rows read like Drive.
  const rows = [];
  const treeLines = [[rootName + '/' +
    (CONFIG.INCLUDE_FILE_COUNTS ? '  [' + (directFiles[CONFIG.ROOT_ID] || 0) + ' loose files at root]' : '')]];
  const nameIndex = {}; // lowercase normalised name -> count, for duplicate flags
  Object.values(folders).forEach((f) => {
    const k = normalise_(f.name);
    nameIndex[k] = (nameIndex[k] || 0) + 1;
  });

  function walk(parentId, parentPath, depth) {
    const kids = (children[parentId] || []).map((id) => folders[id])
      .sort((a, b) => a.name.localeCompare(b.name));
    const seenHere = {};
    kids.forEach((f) => {
      const path = parentPath + '/' + f.name.trim();
      const subCount = (children[f.id] || []).length;
      const fileCount = directFiles[f.id] || 0;
      const total = countTotal_(f.id, children, directFiles);
      const norm = normalise_(f.name);
      const flags = [];
      if (seenHere[norm]) flags.push('DUP_SAME_PARENT');
      seenHere[norm] = true;
      if (nameIndex[norm] > 1) flags.push('DUP_NAME_x' + nameIndex[norm]);
      if (total === 0 && subCount === 0) flags.push('EMPTY');
      if (f.name !== f.name.trim() || /\s{2,}/.test(f.name)) flags.push('WHITESPACE');
      if (/\b(19|20)\d{2}\b|\bFY ?\d{2}/i.test(f.name)) flags.push('YEAR_IN_NAME');
      if (/\b(copy of|untitled|new folder|misc|other|old|temp|backup)\b/i.test(f.name)) flags.push('VAGUE_NAME');
      if (depth >= 6) flags.push('DEEP');
      if (fileCount > 150) flags.push('OVERLOADED');

      rows.push([
        f.id, f.name, depth, path, parentId === CONFIG.ROOT_ID ? '(root)' : parentId,
        subCount, fileCount, shortcuts[f.id] || 0, total,
        (f.createdTime || '').slice(0, 10), (f.modifiedTime || '').slice(0, 10),
        flags.join(', '), 'https://drive.google.com/drive/folders/' + f.id,
      ]);
      treeLines.push(['  '.repeat(depth) + '- ' + f.name.trim() +
        (CONFIG.INCLUDE_FILE_COUNTS ? '  [' + fileCount + ' files]' : '') +
        (flags.length ? '  {' + flags.join(', ') + '}' : '')]);

      if (!CONFIG.MAX_DEPTH || depth < CONFIG.MAX_DEPTH) walk(f.id, path, depth + 1);
    });
  }
  walk(CONFIG.ROOT_ID, '', 1);

  // 3. Write the output sheet.
  const ss = CONFIG.OUTPUT_SPREADSHEET_ID
    ? SpreadsheetApp.openById(CONFIG.OUTPUT_SPREADSHEET_ID)
    : SpreadsheetApp.create('Drive schema - ' + rootName + ' - ' +
        Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HHmm'));

  const header = ['Folder ID', 'Name', 'Depth', 'Path', 'Parent ID', 'Subfolders',
    'Files (direct)', 'Shortcuts (direct)', 'Files (total incl. subfolders)',
    'Created', 'Modified', 'Flags', 'URL'];
  writeSheet_(ss, 'Schema', [header].concat(rows));
  writeSheet_(ss, 'Tree', treeLines);
  if (!ss.getSheetByName('Mapping')) {
    writeSheet_(ss, 'Mapping', [MAPPING_HEADER]);
  }
  const first = ss.getSheets()[0];
  if (first.getName() === 'Sheet1') ss.deleteSheet(first);

  Logger.log('Folders: %s | Items scanned: %s | %ss', rows.length, items.length,
    Math.round((Date.now() - started) / 1000));
  Logger.log('Output: %s', ss.getUrl());
}

// Same header Script 2 expects. Keep the two in sync.
const MAPPING_HEADER = ['Source Folder ID', 'Current Path', 'Action',
  'Target Path', 'New Name', 'Reason', 'Status', 'Result'];

/** Shared drive: list everything in one paginated query per type. */
function listSharedDrive_(driveId) {
  const q = CONFIG.INCLUDE_FILE_COUNTS
    ? 'trashed = false'
    : "trashed = false and mimeType = '" + FOLDER_MIME + "'";
  return pagedList_({ q: q, corpora: 'drive', driveId: driveId });
}

/** Regular folder: breadth-first, batching up to 40 parents per query. */
function listUnderFolder_(rootId) {
  const out = [];
  let frontier = [rootId];
  let depth = 0;
  while (frontier.length && (!CONFIG.MAX_DEPTH || depth < CONFIG.MAX_DEPTH)) {
    const next = [];
    for (let i = 0; i < frontier.length; i += 40) {
      const parents = frontier.slice(i, i + 40).map((id) => "'" + id + "' in parents").join(' or ');
      let q = 'trashed = false and (' + parents + ')';
      if (!CONFIG.INCLUDE_FILE_COUNTS) q += " and mimeType = '" + FOLDER_MIME + "'";
      pagedList_({ q: q, corpora: 'allDrives' }).forEach((it) => {
        out.push(it);
        if (it.mimeType === FOLDER_MIME) next.push(it.id);
      });
    }
    frontier = next;
    depth++;
  }
  return out;
}

function pagedList_(opts) {
  const out = [];
  let pageToken;
  do {
    const res = Drive.Files.list(Object.assign({
      pageSize: 1000,
      pageToken: pageToken,
      includeItemsFromAllDrives: true,
      supportsAllDrives: true,
      fields: 'nextPageToken, files(id, name, mimeType, parents, createdTime, modifiedTime)',
    }, opts));
    (res.files || []).forEach((f) => out.push(f));
    pageToken = res.nextPageToken;
  } while (pageToken);
  return out;
}

function countTotal_(id, children, directFiles) {
  let n = directFiles[id] || 0;
  (children[id] || []).forEach((c) => { n += countTotal_(c, children, directFiles); });
  return n;
}

/** Lowercase, strip punctuation/extra spaces so "Tech Docs " == "tech docs". */
function normalise_(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function writeSheet_(ss, name, values) {
  const sh = ss.getSheetByName(name) || ss.insertSheet(name);
  sh.clear();
  if (!values.length) return;
  const width = Math.max.apply(null, values.map((r) => r.length));
  const padded = values.map((r) => r.concat(Array(width - r.length).fill('')));
  sh.getRange(1, 1, padded.length, width).setValues(padded);
  sh.setFrozenRows(1);
  if (width > 1) sh.getRange(1, 1, 1, width).setFontWeight('bold');
}
