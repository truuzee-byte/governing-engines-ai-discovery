PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS supervisor_tasks (
    task_id TEXT PRIMARY KEY,
    interaction_id TEXT,
    session_id TEXT,
    trace_reference TEXT,
    current_stage TEXT NOT NULL,
    status TEXT NOT NULL,
    active_spec_id TEXT,
    active_spec_hash TEXT,
    mode_state TEXT NOT NULL,
    builder_state TEXT,
    current_component TEXT,
    current_operation TEXT,
    last_operation_result TEXT,
    validation_state TEXT,
    paused INTEGER NOT NULL DEFAULT 0,
    halted INTEGER NOT NULL DEFAULT 0,
    failure_code TEXT,
    failure_detail_json TEXT,
    latest_event_sequence INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS supervisor_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    target TEXT,
    operation TEXT,
    status TEXT,
    message TEXT,
    detail_json TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(task_id, sequence)
);

CREATE TABLE IF NOT EXISTS supervisor_messages (
    message_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    message_type TEXT NOT NULL,
    message TEXT NOT NULL,
    related_event_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivery_state TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mode_responses (
    response_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    response_type TEXT NOT NULL,
    message TEXT NOT NULL,
    current_state TEXT NOT NULL,
    related_event_ids_json TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    requested_action TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS supervisor_commands (
    command_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    command TEXT NOT NULL,
    reason TEXT NOT NULL,
    issued_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    applied_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_task_sequence
ON supervisor_events(task_id, sequence);
CREATE INDEX IF NOT EXISTS idx_messages_task_state
ON supervisor_messages(task_id, delivery_state, created_at);
CREATE INDEX IF NOT EXISTS idx_responses_task
ON mode_responses(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_commands_task
ON supervisor_commands(task_id, created_at);
