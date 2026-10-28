// SocEnt Drive - Script 1: extract folder schema (read-only, no file contents)
// Paste into Code.gs, save (Ctrl+S), choose extractSchema, click Run.
// Needs: Services > + > Drive API > Add.

const CONFIG = {
  ROOT_ID: '0AGUWPWZlmPBEUk9PVA',  // SocEnt shared drive
  INCLUDE_FILE_COUNTS: true,
  MAX_DEPTH: 0,                     // 0 = all levels
  OUTPUT_SPREADSHEET_ID: '',        // blank = create a new sheet
};

const FOLDER_MIME = 'application/vnd.google-apps.folder';
const SHORTCUT_MIME = 'application/vnd.google-apps.shortcut';

function extractSchema() {
  const started = Date.now();
  const isSharedDrive = CONFIG.ROOT_ID.startsWith('0A');
  const rootName = isSharedDrive
    ? Drive.Drives.get(CONFIG.ROOT_ID).name
    : Drive.Files.get(CONFIG.ROOT_ID, { supportsAllDrives: true, fields: 'name' }).name;

  const items = isSharedDrive ? listSharedDrive_(CONFIG.ROOT_ID) : listUnderFolder_(CONFIG.ROOT_ID);
  const folders = {};
  const children = {};
  const directFiles = {};
  const shortcuts = {};
  items.forEach(function (it) {
    const parent = (it.parents || [])[0];
    if (it.mimeType === FOLDER_MIME) {
      folders[it.id] = it;
      (children[parent] = children[parent] || []).push(it.id);
    } else if (parent) {
      directFiles[parent] = (directFiles[parent] || 0) + 1;
      if (it.mimeType === SHORTCUT_MIME) shortcuts[parent] = (shortcuts[parent] || 0) + 1;
    }
  });

  const rows = [];
  const treeLines = [[rootName + '/' +
    (CONFIG.INCLUDE_FILE_COUNTS ? '  [' + (directFiles[CONFIG.ROOT_ID] || 0) + ' loose files at root]' : '')]];
  const nameIndex = {};
  Object.keys(folders).forEach(function (id) {
    const k = normalise_(folders[id].name);
    nameIndex[k] = (nameIndex[k] || 0) + 1;
  });

  function walk(parentId, parentPath, depth) {
    const kids = (children[parentId] || [])
      .map(function (id) { return folders[id]; })
      .sort(function (a, b) { return a.name.localeCompare(b.name); });
    const seenHere = {};
    kids.forEach(function (f) {
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
        flags.join(', '), 'https://drive.google.com/drive/folders/' + f.id
      ]);
      treeLines.push(['  '.repeat(depth) + '- ' + f.name.trim() +
        (CONFIG.INCLUDE_FILE_COUNTS ? '  [' + fileCount + ' files]' : '') +
        (flags.length ? '  {' + flags.join(', ') + '}' : '')]);

      if (!CONFIG.MAX_DEPTH || depth < CONFIG.MAX_DEPTH) walk(f.id, path, depth + 1);
    });
  }
  walk(CONFIG.ROOT_ID, '', 1);

  const ss = CONFIG.OUTPUT_SPREADSHEET_ID
    ? SpreadsheetApp.openById(CONFIG.OUTPUT_SPREADSHEET_ID)
    : SpreadsheetApp.create('Drive schema - ' + rootName + ' - ' +
        Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HHmm'));

  const header = ['Folder ID', 'Name', 'Depth', 'Path', 'Parent ID', 'Subfolders',
    'Files (direct)', 'Shortcuts (direct)', 'Files (total incl. subfolders)',
    'Created', 'Modified', 'Flags', 'URL'];
  writeSheet_(ss, 'Schema', [header].concat(rows));
  writeSheet_(ss, 'Tree', treeLines);
  const first = ss.getSheets()[0];
  if (first.getName() === 'Sheet1') ss.deleteSheet(first);

  Logger.log('Folders: %s | Items scanned: %s | %ss', rows.length, items.length,
    Math.round((Date.now() - started) / 1000));
  Logger.log('Output: %s', ss.getUrl());
}

function listSharedDrive_(driveId) {
  const q = CONFIG.INCLUDE_FILE_COUNTS
    ? 'trashed = false'
    : "trashed = false and mimeType = '" + FOLDER_MIME + "'";
  return pagedList_({ q: q, corpora: 'drive', driveId: driveId });
}

function listUnderFolder_(rootId) {
  const out = [];
  let frontier = [rootId];
  let depth = 0;
  while (frontier.length && (!CONFIG.MAX_DEPTH || depth < CONFIG.MAX_DEPTH)) {
    const next = [];
    for (let i = 0; i < frontier.length; i += 40) {
      const parents = frontier.slice(i, i + 40)
        .map(function (id) { return "'" + id + "' in parents"; }).join(' or ');
      let q = 'trashed = false and (' + parents + ')';
      if (!CONFIG.INCLUDE_FILE_COUNTS) q += " and mimeType = '" + FOLDER_MIME + "'";
      pagedList_({ q: q, corpora: 'allDrives' }).forEach(function (it) {
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
      fields: 'nextPageToken, files(id, name, mimeType, parents, createdTime, modifiedTime)'
    }, opts));
    (res.files || []).forEach(function (f) { out.push(f); });
    pageToken = res.nextPageToken;
  } while (pageToken);
  return out;
}

function countTotal_(id, children, directFiles) {
  let n = directFiles[id] || 0;
  (children[id] || []).forEach(function (c) { n += countTotal_(c, children, directFiles); });
  return n;
}

function normalise_(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function writeSheet_(ss, name, values) {
  const sh = ss.getSheetByName(name) || ss.insertSheet(name);
  sh.clear();
  if (!values.length) return;
  const width = Math.max.apply(null, values.map(function (r) { return r.length; }));
  const padded = values.map(function (r) { return r.concat(Array(width - r.length).fill('')); });
  sh.getRange(1, 1, padded.length, width).setValues(padded);
  sh.setFrozenRows(1);
  if (width > 1) sh.getRange(1, 1, 1, width).setFontWeight('bold');
}
