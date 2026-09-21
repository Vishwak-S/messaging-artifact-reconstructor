// Canonical TypeScript types mirroring the backend Pydantic schemas

export interface Case {
  id: number;
  case_id: string;
  name: string;
  description?: string;
  investigator?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface Evidence {
  id: number;
  evidence_id: string;
  case_id: string;
  original_filename: string;
  original_size_bytes?: number;
  sha256_hash?: string;
  import_timestamp: string;
  status: string;
  app_detected?: string;
  detection_confidence?: string;
  detection_reasons?: string[];
  is_encrypted: boolean;
}

export interface ForensicDatabase {
  id: number;
  db_id: string;
  evidence_id: string;
  case_id: string;
  db_filename: string;
  app_detected?: string;
  detection_confidence?: string;
  detection_reasons?: string[];
  table_count?: number;
  total_records?: number;
  sqlite_valid: boolean;
  wal_detected: boolean;
  shm_detected: boolean;
  journal_detected: boolean;
  page_size?: number;
  schema_info?: Record<string, string[]>;
  analyzed_at?: string;
}

export interface Conversation {
  id: number;
  conv_id: string;
  db_id: string;
  case_id: string;
  application?: string;
  display_name?: string;
  participants?: string[];
  message_count: number;
  first_message_ts?: string;
  last_message_ts?: string;
  is_group: boolean;
  group_name?: string;
}

export interface Message {
  id: number;
  message_id: string;
  conv_id?: string;
  case_id: string;
  evidence_id: string;
  db_id: string;
  application?: string;
  sender?: string;
  recipient?: string;
  message_text?: string;
  message_type: string;
  direction?: string;
  status?: string;
  evidence_status: string;
  timestamp?: string;
  timestamp_original?: string;
  timezone_info?: string;
  has_attachment: boolean;
  attachment_name?: string;
  attachment_found?: boolean;
  attachment_sha256?: string;
  source_database?: string;
  source_table?: string;
  source_column?: string;
  source_record?: string;
  raw_record?: Record<string, unknown>;
  extraction_method?: string;
  parser_version?: string;
  confidence: string;
}

export interface TimelineEntry {
  timestamp?: string;
  timestamp_original?: string;
  application?: string;
  sender?: string;
  message_type: string;
  message_text?: string;
  conv_id?: string;
  message_id: string;
  evidence_status: string;
}

export interface SearchResult {
  total: number;
  page: number;
  page_size: number;
  results: Message[];
}

export interface AnalysisRun {
  id: number;
  run_id: string;
  case_id: string;
  evidence_id: string;
  start_time: string;
  end_time?: string;
  status: string;
  parser_versions?: Record<string, string>;
  files_analyzed: number;
  messages_extracted: number;
  conversations_found: number;
  attachments_found: number;
  warnings?: string[];
  errors?: string[];
  pipeline_log?: Array<{ step: string; status: string; detail: string; ts: string }>;
}

export interface AuditEvent {
  id: number;
  case_id?: string;
  evidence_id?: string;
  timestamp: string;
  action: string;
  description?: string;
}

export interface Report {
  id: number;
  report_id: string;
  case_id: string;
  format: string;
  generated_at: string;
  file_size_bytes?: number;
}

export interface Stats {
  total_cases: number;
  total_evidence: number;
  total_databases: number;
  total_messages: number;
  total_conversations: number;
  total_attachments: number;
  applications: { WhatsApp: number; Telegram: number; Signal: number };
}

export interface TableRowsResponse {
  database: string;
  table: string;
  total_rows: number;
  page: number;
  page_size: number;
  columns: string[];
  rows: Record<string, unknown>[];
}
