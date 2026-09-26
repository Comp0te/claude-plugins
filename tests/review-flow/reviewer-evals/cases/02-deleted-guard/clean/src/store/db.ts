export interface UserRecord {
  id: string;
  email: string;
}

const users = new Map<string, UserRecord>([
  ["1", { id: "1", email: "ada@example.com" }],
  ["2", { id: "2", email: "grace@example.com" }],
  ["3", { id: "3", email: "margaret@example.com" }],
]);

export function getUser(id: string): UserRecord | undefined {
  return users.get(id);
}

export function deleteUserRecord(id: string): boolean {
  return users.delete(id);
}

export function listUsers(): UserRecord[] {
  return [...users.values()];
}
