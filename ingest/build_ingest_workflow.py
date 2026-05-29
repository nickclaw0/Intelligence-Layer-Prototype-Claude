#!/usr/bin/env python3
"""Generate the Phase 3 ingest pipeline as an import-ready n8n workflow.

The pipeline watches the Google Drive `Ingest/` folder, normalises each new
raw file into the `raw/...` tree under the naming convention, computes its
sha256 content hash, dedupes against `raw/_manifest.json`, appends a manifest
entry, writes the manifest back to Drive, and triggers the daily lint so the
new source folds into the wiki.

This emits a template (placeholder credentials, REPLACE_ markers) exactly like
the project's other n8n packs. Import it into n8n, attach Google Drive + GitHub
credentials, set the instance values, then activate. No Node needed to build it.

Usage:
    python3 ingest/build_ingest_workflow.py     # writes ingest/velorixa-ingest-pipeline.n8n.json
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "ingest" / "velorixa-ingest-pipeline.n8n.json"

# The Code node body that does the real normalisation work.
NORMALIZE_JS = r"""
// Normalise one ingested Drive file into a canonical raw entry.
// Input: the Google Drive file metadata (name, id, size) + downloaded binary.
const crypto = require('crypto');

const meta = $input.first().json;
const bin = $input.first().binary && $input.first().binary.data;
const originalName = meta.name || meta.originalFilename || 'unknown';
const driveFileId = meta.id || '';
const sizeBytes = Number(meta.size || (bin && bin.fileSize) || 0);

// Content hash over the downloaded bytes (Phase 3 keeps content-hash as the
// canonical id until Drive file IDs are reconciled in; see manifest notes).
let buf = Buffer.from('');
if (bin && bin.data) { buf = Buffer.from(bin.data, 'base64'); }
const sha = crypto.createHash('sha256').update(buf).digest('hex');
const shortRef = sha.slice(0, 8);

// Tenant defaults for this single-tenant prototype.
const client = 'velorixa';
const therapeuticArea = 'insomnia';
const project = 'launch-prep';

// Expected convention: YYYY-MM-DD_VLX_<type>_<slug>_vN.ext
// If the file does not match, route it to manual review rather than guessing.
const NAME_RE = /^(\d{4}-\d{2}-\d{2})_([A-Z0-9]+)_([a-z-]+)_(.+)_v(\d+)\.(\w+)$/;
const m = originalName.match(NAME_RE);

let supported = false;
let sourceType = 'unknown';
let ext = (originalName.split('.').pop() || '').toLowerCase();
const SUPPORTED_EXT = ['txt','md','pdf','docx','doc','pptx','ppt','xlsx','xls','csv','json'];
if (m) {
  sourceType = m[3];
  ext = m[6].toLowerCase();
  supported = SUPPORTED_EXT.includes(ext);
}

const currentPath = `raw/${client}/${therapeuticArea}/${project}/${sourceType}/${originalName}`;

const entry = {
  id: sha,                       // content-hash for now (id_type below)
  id_type: 'content-hash',
  short_ref: shortRef,
  current_path: currentPath,
  content_hash: `sha256:${sha}`,
  original_filename: originalName,
  client,
  therapeutic_area: therapeuticArea,
  project,
  source_type: sourceType,
  classification: 'client-confidential',   // default high; reviewer may downgrade
  size_bytes: sizeBytes,
  drive_file_id: driveFileId,              // captured for Phase 3 reconciliation
  ingest_history: [{
    event: 'n8n-ingest',
    timestamp: new Date().toISOString(),
    actor: 'n8n-ingest-pipeline',
    from: `Ingest/${originalName}`,
    version: m ? Number(m[5]) : 1,
    note: 'Auto-ingested from Drive Ingest/ folder.'
  }]
};

return [{ json: { supported, naming_ok: !!m, entry, sha, shortRef, currentPath, originalName } }];
""".strip()

UPDATE_MANIFEST_JS = r"""
// Merge the new entry into the existing manifest, deduping by content hash.
// Inputs: item 0 = normalised entry (from "Normalize And Hash"),
//         item 1 = current _manifest.json contents (from "Read Manifest").
const normalized = $('Normalize And Hash').first().json;
const manifestRaw = $('Read Manifest').first().json;

let manifest;
try {
  manifest = typeof manifestRaw.data === 'string'
    ? JSON.parse(manifestRaw.data)
    : (manifestRaw.text ? JSON.parse(manifestRaw.text) : manifestRaw);
} catch (e) {
  manifest = { manifest_version: 1, sources: [] };
}
manifest.sources = manifest.sources || [];

const exists = manifest.sources.some(s => s.id === normalized.entry.id
  || s.content_hash === normalized.entry.content_hash);

let action = 'appended';
if (exists) {
  action = 'duplicate';
} else {
  manifest.sources.push(normalized.entry);
  manifest.last_updated = new Date().toISOString();
}

return [{ json: {
  action,
  is_new: !exists,
  manifest_json: JSON.stringify(manifest, null, 2),
  short_ref: normalized.shortRef
} }];
""".strip()

REVIEW_JS = r"""
// Build a review record for files that do not match the naming convention or
// are an unsupported type. Surfaced, never silently dropped.
const n = $('Normalize And Hash').first().json;
return [{ json: {
  status: 'needs-review',
  reason: !n.naming_ok ? 'filename does not match YYYY-MM-DD_VLX_<type>_<slug>_vN.ext'
                       : 'unsupported file type',
  original_filename: n.originalName
} }];
""".strip()


def node(name, ntype, version, params, pos, extra=None):
    n = {
        "parameters": params,
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "type": ntype,
        "typeVersion": version,
        "position": pos,
    }
    if extra:
        n.update(extra)
    return n


def build():
    nodes = [
        node("Drive Ingest Trigger", "n8n-nodes-base.googleDriveTrigger", 1, {
            "event": "fileCreated",
            "triggerOn": "specificFolder",
            "folderToWatch": {"__rl": True, "mode": "list", "value": "REPLACE_WITH_INGEST_FOLDER_ID"},
            "options": {},
        }, [0, 0], {"credentials": {"googleDriveOAuth2Api": {"id": "REPLACE", "name": "Google Drive account"}}}),

        node("Download Ingested File", "n8n-nodes-base.googleDrive", 3, {
            "operation": "download",
            "fileId": {"__rl": True, "mode": "id", "value": "={{ $json.id }}"},
            "options": {},
        }, [220, 0], {"credentials": {"googleDriveOAuth2Api": {"id": "REPLACE", "name": "Google Drive account"}}}),

        node("Normalize And Hash", "n8n-nodes-base.code", 2, {
            "jsCode": NORMALIZE_JS,
        }, [440, 0]),

        node("IF Supported And Named", "n8n-nodes-base.if", 2.3, {
            "conditions": {
                "options": {"caseSensitive": True, "typeValidation": "loose"},
                "combinator": "and",
                "conditions": [
                    {"leftValue": "={{ $json.supported }}", "rightValue": True,
                     "operator": {"type": "boolean", "operation": "true", "singleValue": True}},
                    {"leftValue": "={{ $json.naming_ok }}", "rightValue": True,
                     "operator": {"type": "boolean", "operation": "true", "singleValue": True}},
                ],
            },
            "options": {},
        }, [660, 0]),

        node("Read Manifest", "n8n-nodes-base.googleDrive", 3, {
            "operation": "download",
            "fileId": {"__rl": True, "mode": "id", "value": "REPLACE_WITH_MANIFEST_FILE_ID"},
            "options": {},
        }, [880, -120], {"credentials": {"googleDriveOAuth2Api": {"id": "REPLACE", "name": "Google Drive account"}}}),

        node("Move File Into Raw", "n8n-nodes-base.googleDrive", 3, {
            "operation": "move",
            "fileId": {"__rl": True, "mode": "id", "value": "={{ $('Drive Ingest Trigger').item.json.id }}"},
            "driveId": {"__rl": True, "mode": "list", "value": "My Drive"},
            "folderId": {"__rl": True, "mode": "id", "value": "REPLACE_WITH_RAW_FOLDER_ID"},
            "options": {},
        }, [880, 120], {"credentials": {"googleDriveOAuth2Api": {"id": "REPLACE", "name": "Google Drive account"}}}),

        node("Update Manifest", "n8n-nodes-base.code", 2, {
            "jsCode": UPDATE_MANIFEST_JS,
        }, [1100, -120]),

        node("IF New Source", "n8n-nodes-base.if", 2.3, {
            "conditions": {
                "options": {"caseSensitive": True, "typeValidation": "loose"},
                "combinator": "and",
                "conditions": [
                    {"leftValue": "={{ $json.is_new }}", "rightValue": True,
                     "operator": {"type": "boolean", "operation": "true", "singleValue": True}},
                ],
            },
            "options": {},
        }, [1320, -120]),

        node("Write Manifest To Drive", "n8n-nodes-base.googleDrive", 3, {
            "operation": "update",
            "fileId": {"__rl": True, "mode": "id", "value": "REPLACE_WITH_MANIFEST_FILE_ID"},
            "changeFileContent": True,
            "newUpdatedContent": "={{ $json.manifest_json }}",
            "options": {},
        }, [1540, -200], {"credentials": {"googleDriveOAuth2Api": {"id": "REPLACE", "name": "Google Drive account"}}}),

        node("Trigger Daily Lint", "n8n-nodes-base.httpRequest", 4.2, {
            "method": "POST",
            "url": "https://api.github.com/repos/nickclaw0/Intelligence-Layer-Prototype-Claude/dispatches",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Authorization", "value": "Bearer REPLACE_WITH_GITHUB_PAT"},
                {"name": "Accept", "value": "application/vnd.github+json"},
                {"name": "User-Agent", "value": "velorixa-ingest"},
            ]},
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ event_type: 'raw-ingested', client_payload: { short_ref: $json.short_ref } }) }}",
            "options": {},
        }, [1760, -200]),

        node("Duplicate Source Skipped", "n8n-nodes-base.noOp", 1, {}, [1540, -40]),

        node("Build Review Record", "n8n-nodes-base.code", 2, {
            "jsCode": REVIEW_JS,
        }, [880, 320]),

        node("Log Review For Human", "n8n-nodes-base.noOp", 1, {}, [1100, 320]),
    ]

    connections = {
        "Drive Ingest Trigger": {"main": [[{"node": "Download Ingested File", "type": "main", "index": 0}]]},
        "Download Ingested File": {"main": [[{"node": "Normalize And Hash", "type": "main", "index": 0}]]},
        "Normalize And Hash": {"main": [[{"node": "IF Supported And Named", "type": "main", "index": 0}]]},
        "IF Supported And Named": {"main": [
            [{"node": "Read Manifest", "type": "main", "index": 0},
             {"node": "Move File Into Raw", "type": "main", "index": 0}],
            [{"node": "Build Review Record", "type": "main", "index": 0}],
        ]},
        "Read Manifest": {"main": [[{"node": "Update Manifest", "type": "main", "index": 0}]]},
        "Update Manifest": {"main": [[{"node": "IF New Source", "type": "main", "index": 0}]]},
        "IF New Source": {"main": [
            [{"node": "Write Manifest To Drive", "type": "main", "index": 0}],
            [{"node": "Duplicate Source Skipped", "type": "main", "index": 0}],
        ]},
        "Write Manifest To Drive": {"main": [[{"node": "Trigger Daily Lint", "type": "main", "index": 0}]]},
        "Build Review Record": {"main": [[{"node": "Log Review For Human", "type": "main", "index": 0}]]},
    }

    return {
        "name": "Velorixa Intelligence Layer_Ingest",
        "nodes": nodes,
        "connections": connections,
        "pinData": {},
        "settings": {"executionOrder": "v1", "saveManualExecutions": True, "callerPolicy": "workflowsFromSameOwner"},
        "staticData": None,
        "tags": [],
    }


def main():
    wf = build()
    # sanity: every connection target exists
    names = {n["name"] for n in wf["nodes"]}
    for src, conn in wf["connections"].items():
        assert src in names, f"connection source {src} not a node"
        for outputs in conn["main"]:
            for c in outputs:
                assert c["node"] in names, f"connection target {c['node']} not a node"
    OUT.write_text(json.dumps(wf, indent=2))
    print(f"built {OUT.relative_to(REPO)}: {len(wf['nodes'])} nodes, "
          f"{len(wf['connections'])} wired nodes")


if __name__ == "__main__":
    main()
