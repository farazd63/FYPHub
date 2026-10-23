import { test } from "node:test";
import { strict as assert } from "node:assert";
import { chatLabel, canStartMatch } from "../src/matchChatView.mjs";
test("only a matching category enables a chat", () => { assert.equal(canStartMatch(0), false); assert.equal(canStartMatch(1), true); });
test("closed chats are labelled", () => { assert.equal(chatLabel(null), "Open"); assert.equal(chatLabel("2026-01-01T00:00:00Z"), "Closed"); });
