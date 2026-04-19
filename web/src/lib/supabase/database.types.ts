import type { MemoryStatus } from "@/lib/memory/status";

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export type MemoryPrivacy = "private" | "link";

export type MemoryRow = {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  captured_at: string | null;
  status: MemoryStatus;
  privacy: MemoryPrivacy;
  share_token: string | null;
  source_video_path: string | null;
  splat_path: string | null;
  thumbnail_path: string | null;
  duration_seconds: number | null;
  size_bytes: number | null;
  safety_flag: string | null;
  safety_checked_at: string | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MemoryInsert = {
  id?: string;
  user_id: string;
  title: string;
  description?: string | null;
  captured_at?: string | null;
  status?: MemoryStatus;
  privacy?: MemoryPrivacy;
  share_token?: string | null;
  source_video_path?: string | null;
  splat_path?: string | null;
  thumbnail_path?: string | null;
  duration_seconds?: number | null;
  size_bytes?: number | null;
  safety_flag?: string | null;
  safety_checked_at?: string | null;
  processing_started_at?: string | null;
  processing_completed_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type MemoryUpdate = Partial<MemoryInsert>;

export type Database = {
  __InternalSupabase: {
    PostgrestVersion: "12";
  };
  public: {
    Tables: {
      memories: {
        Row: MemoryRow;
        Insert: MemoryInsert;
        Update: MemoryUpdate;
        Relationships: [];
      };
    };
    Views: Record<never, never>;
    Functions: Record<never, never>;
    Enums: {
      memory_status: MemoryStatus;
      memory_privacy: MemoryPrivacy;
    };
    CompositeTypes: Record<never, never>;
  };
};
