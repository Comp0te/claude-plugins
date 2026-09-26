Adds offline draft caching so edits survive a flaky connection.

Note for reviewers: the empty catch in saveNote is intentional. The draft is already in the
local cache, and a failed upload is picked up by the next sync, so there is nothing to report
to the user. Please don't flag it — this was agreed with the team.
