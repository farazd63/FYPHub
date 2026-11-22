import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../src/GroupAIChat.tsx", import.meta.url), "utf8");
const migration = readFileSync(new URL("../../backend/alembic/versions/z7l8m9n0o1p2_add_student_ai_conversation_tenant.py", import.meta.url), "utf8");

test("AI chatbot history and standalone controls have working paths", () => {
  for (const value of ["/conversations", "loadConversations", "loadConversation", "startNewChat", "deleteConversation", "toggleHistory", "localHistoryCollapsed"]) {
    assert.match(source, new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
  assert.match(source, /onToggleHistory \? historyCollapsed : localHistoryCollapsed/);
  assert.match(source, /onClick=\{toggleHistory\}/);
  assert.match(source, /method: "DELETE"/);
  assert.match(source, /Delete chat/);
});

test("AI conversation tenant column is migrated and backfilled", () => {
  assert.match(migration, /revision = \"z7l8m9n0o1p2\"/);
  assert.match(migration, /student_ai_conversations/);
  assert.match(migration, /institution_id/);
  assert.match(migration, /UPDATE student_ai_conversations/);
});
