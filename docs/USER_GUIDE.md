# PolyPilot user guide

## 0. Account
Register, then sign in — or click **Continue with Google** (shown when the server has Google
sign-in configured). If you first registered with a password and then use Google with the same
email, the accounts are merged; if that email was never confirmed, the old password stops working
and you can set a new one with **Forgot password?**. Forgot your password? Click **Forgot password?** on the sign-in page. A reset
link is emailed to you; it works once and expires after 30 minutes. In local development without an
email server, the link appears in the backend console. Resetting signs you out everywhere.

## 0.1 Choose an AI provider
Open **AI Providers**. Click **Add key** on any provider (Gemini, Claude, OpenAI, DeepSeek, Groq,
Mistral, xAI, OpenRouter, Together, Fireworks, Cerebras), paste your API key (**Get a key** links to
the provider's key page), pick a model, and **Save key**. The key is checked right away by listing
the models it can use; pick one from the Model list if yours is not available. Your first saved
provider becomes active; switch with **Use this**, or **Use server default** to go back to the key
configured by the administrator. Keys are stored encrypted and never shown again.

## 1. Create a problem
**Create Problem** → enter the title, idea, intended algorithm, constraints, input/output formats and
limits → save. The draft is stored on the server, and only you can see it.

## 2. Generate artifacts
In the workspace, click **Generate with AI**. PolyPilot asks the configured model for a specification,
statement, reference solution, brute-force solution, validator, generator and editorial, and shows
progress step by step. Your daily AI quota is shown under **AI Provider**.

## 3. Review generated content
Open each tab (Statement, Editorial, Solutions, Validator, Generators) and read the output.
**Generated code is not trusted** until it passes the checks below.

Editing and saving artifacts in the UI is **not implemented yet**, and neither is a per-step
"regenerate" button. Through the API you can regenerate one step
(`POST /api/v1/problems/{id}/regenerate-step` with `{"step": "validator"}`) or save new content
(`PATCH /api/v1/artifacts/{id}` with `{"content": …}`, authenticated). Each saved change bumps the
artifact version, and verification is tied to the exact source hash, so edited code must be
re-verified.

## 4. Build and validate tests (Test Cases tab)
- **Import samples** from the specification. You can also add manual tests, upload a text file,
  or tick "invalid" for inputs the validator must reject.
- **Run validator** checks that the validator accepts every valid input and rejects every invalid
  one, including five generated malformed inputs.
- **Generate** runs `gen <type> <seed>` for a range of seeds. Only inputs the validator accepts are
  saved, and each seed is recorded so you can reproduce the test.

## 5. Verify solutions (Verification tab)
- **Solution testing → Reference: Run on all tests.** You can tick "store outputs as expected
  answers"; the reference becomes the oracle, which is evidence, not proof.
- **Test a candidate** with an optional expected verdict (WA/TLE/…). TLE is re-run before PolyPilot
  reports it, and unstable timings show as `TLE?`.

## 6. Differential and stress testing
- **Differential:** compares the reference with the brute force on many small generated inputs.
- **Stress:** compares the reference with any candidate.

Set the iterations, seed, time limits and an overall budget. Progress and the current seed are
shown live, and **Stop** cancels after the current batch.

## 7. Inspect counterexamples
The **Counterexamples** view shows the failing input, a minimized input (still valid and still
failing), both outputs and stderr. You can copy or download any of these.

## 8. Repair a failing solution
**Propose repair** makes exactly one AI call and shows the suspected bug, an explanation and a
diff. **Accept & re-test** runs the repaired code on the counterexample plus your full test suite;
your original artifact is never overwritten. Reject anything you don't trust.

## 9. Connect Polygon
**Polygon Integration** (sidebar) → enter your Polygon API key and secret. They're stored encrypted
and never shown again. Then click **Test connection**, which only lists your problems.

## 10. Synchronize and build
In the workspace **Polygon** tab:
1. **Connect existing** (retype the problem name to confirm) or **Create new**.
2. **Preview** shows local items only, plus their verification status. Validators and
   checkers that are unverified or failed are blocked.
3. **Dry run** reads Polygon and lists the exact create/update/conflict actions. Nothing is written.
4. **Upload** writes those changes to your Polygon *working copy* only. Conflicting remote files are
   left untouched unless you tick "overwrite".
5. **Commit** asks you to type the problem ID; it commits the working copy and shows the old and new
   revision.
6. **Build package** runs preflight checks, asks you to type the problem ID again, and then shows the
   real package state (submitted → building → built/failed).

**History** lists every Polygon operation with its API requests. Secrets are never recorded.
