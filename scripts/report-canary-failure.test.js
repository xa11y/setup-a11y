"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { reportCanaryFailure, TITLE } = require("./report-canary-failure");

function fixture(openIssues = []) {
  const created = [];
  const messages = [];
  const github = {
    paginate: async (_method, request) => {
      assert.deepEqual(request, {
        owner: "xa11y",
        repo: "setup-a11y",
        state: "open",
        per_page: 100,
      });
      return openIssues;
    },
    rest: {
      issues: {
        listForRepo() {},
        create: async (issue) => created.push(issue),
      },
    },
  };
  const context = {
    repo: { owner: "xa11y", repo: "setup-a11y" },
    serverUrl: "https://github.com",
    runId: 123,
    payload: { inputs: { ref: "main" } },
  };
  const core = { info: (message) => messages.push(message) };
  return { github, context, core, created, messages };
}

test("opens an issue containing the failed run", async () => {
  const f = fixture();
  await reportCanaryFailure(f);
  assert.equal(f.created.length, 1);
  assert.equal(f.created[0].title, TITLE);
  assert.match(f.created[0].body, /actions\/runs\/123/);
  assert.match(f.created[0].body, /xa11y\/xa11y ref `main`/);
});

test("reuses an existing open issue", async () => {
  const f = fixture([{ number: 7, title: TITLE }]);
  await reportCanaryFailure(f);
  assert.equal(f.created.length, 0);
  assert.equal(f.messages.length, 1);
});

test("a pull request with the same title does not suppress an issue", async () => {
  const f = fixture([{ title: TITLE, pull_request: {} }]);
  await reportCanaryFailure(f);
  assert.equal(f.created.length, 1);
});

test("API failures surface instead of silently dropping an alert", async () => {
  const f = fixture();
  f.github.rest.issues.create = async () => {
    throw new Error("create failed");
  };
  await assert.rejects(reportCanaryFailure(f), /create failed/);
});
