"use strict";

const TITLE = "Daily setup-a11y canary failed";

async function reportCanaryFailure({ github, context, core }) {
  const { owner, repo } = context.repo;
  const openIssues = await github.paginate(github.rest.issues.listForRepo, {
    owner,
    repo,
    state: "open",
    per_page: 100,
  });
  if (openIssues.some((issue) => !issue.pull_request && issue.title === TITLE)) {
    core.info("The canary failure already has an open issue.");
    return;
  }

  const runUrl = `${context.serverUrl}/${owner}/${repo}/actions/runs/${context.runId}`;
  const consumerRef = context.payload.inputs?.ref || "main";
  const body = [
    "The daily canary failed while testing the released `setup-a11y@v1` action",
    `against xa11y/xa11y ref \`${consumerRef}\`.`,
    "",
    `Failed run: ${runUrl}`,
    "",
    "Check the dependency installation, D-Bus/AT-SPI probe, and xa11y test logs.",
    "Close this issue after a successful canary run confirms the fix.",
  ].join("\n");
  await github.rest.issues.create({ owner, repo, title: TITLE, body });
}

module.exports = { reportCanaryFailure, TITLE };
