import { NotFoundError } from "../errors";
import { deleteUserRecord, getUser } from "../store/db";
import { recordDeletion } from "../util/audit";

export interface Actor {
  id: string;
  roles: string[];
}

export async function deleteUsers(actor: Actor, ids: string[]): Promise<void> {
  for (const id of ids) {
    const existing = getUser(id);
    if (!existing) {
      throw new NotFoundError(`user ${id} not found`);
    }
    deleteUserRecord(id);
  }
  recordDeletion(actor.id, ids);
}
