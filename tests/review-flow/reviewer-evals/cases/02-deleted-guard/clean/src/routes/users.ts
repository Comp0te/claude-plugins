import { deleteUsers, Actor } from "../api/users";
import { ForbiddenError } from "../errors";
export interface DeleteUsersRequest {
  actor: Actor;
  params: { ids: string[] };
}

function requireAdmin(actor: Actor): void {
  if (!actor.roles.includes("admin")) {
    throw new ForbiddenError(`${actor.id} lacks admin role`);
  }
}

export async function handleDeleteUsers(req: DeleteUsersRequest): Promise<{ status: number }> {
  requireAdmin(req.actor);
  await deleteUsers(req.actor, req.params.ids);
  return { status: 204 };
}

export async function handleListUsers(): Promise<{ status: number }> {
  return { status: 200 };
}
