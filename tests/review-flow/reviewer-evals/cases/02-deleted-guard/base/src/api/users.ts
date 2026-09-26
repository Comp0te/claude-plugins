import { ForbiddenError, NotFoundError } from "../errors";
import { deleteUserRecord, getUser } from "../store/db";

export interface Actor {
  id: string;
  roles: string[];
}

export async function deleteUser(actor: Actor, id: string): Promise<void> {
  if (!actor.roles.includes("admin")) {
    throw new ForbiddenError(`${actor.id} lacks admin role`);
  }
  const existing = getUser(id);
  if (!existing) {
    throw new NotFoundError(`user ${id} not found`);
  }
  deleteUserRecord(id);
}
