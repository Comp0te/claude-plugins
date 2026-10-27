export interface Record {
  id: string;
  payload: string;
  version: number;
}

export interface Remote {
  push(record: Record): Promise<void>;
}

export interface Store {
  pending(): Record[];
  markSynced(id: string): void;
}
