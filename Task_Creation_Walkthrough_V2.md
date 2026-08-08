# Takehome: Improving an AI Agent's Pass Rate on a Hardware Design Task

## Background

We build evaluation tasks for AI coding agents. An AI agent is given a hardware design problem — a specification and a skeleton of SystemVerilog code — and must write a complete, functionally correct implementation. The agent's solution is then graded by a hidden testbench that checks for cycle-exact correctness. It is like an exam problem for a student, where the student is given a problem statement and a skeleton code, and must write the complete solution. The professor has an automated grading system to grade the student's solution.
We also provide a golden solution that acts as a training point for the AI agent, this golden solution contains the correct implementation of the requirements mentioned in the prompt and the specification and should always pass the testbench.

Your job in this takehome is to **create the golden solution, analyze how an AI agent succeeds at a specific task, then modify the specification to make the problem require deeper reasoning, thereby lowering its pass rate — without making the task unfair**.

You are given a task where an AI agent (Claude Sonnet) achieves approximately **70% pass rate** across 10 independent attempts. Your goal is to modify the prompt/specification so that the agent's pass rate drops to **between 10% and 50%** (out of at least 10 runs), while every behavior the hidden testbench grades remains fully derivable from the specification by a careful engineer. You are hardening the exam, not sabotaging it.

---



## Section 0: Setup (~15 min)

**Tool Installations:**

Install the following if you don't already have them:

- [github.com](http://github.com) account
- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [Cursor IDE](https://cursor.com) (Optional, any editor should be fine)
- [Git](https://git-scm.com/downloads)
- [Python 3.10+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Icarus Verilog](https://steveicarus.github.io/iverilog/usage/installation.html) (`brew install icarus-verilog` on Mac, `apt install iverilog` on Linux)
- HUD account (you should have received an invite — let us know if not). Traces and job results live at [hud.ai](https://hud.ai).

**Windows users:** You will need WSL. Follow the instructions in: [WSL Guide](https://docs.google.com/document/d/1LF0nSO5fTD7e_OC6GThE4AWRrnbPHl7Sz-8rnBxjEiM/edit?usp=sharing) (sections 3.1–3.5).

**ANTHROPIC KEY:** You will also need an **Anthropic API key** (for calling the AI agent). Please check the mail that you received for your API Key.

**Github setup:**

You will fork one repository (the problem-solving repo) and clone the framework repo. Recommended: please open two terminals, one for problem solving and another for setting up the framework.

**Problem solving repo (use your Terminal 1):** Forking gives you your own copy of the repo (with all branches included) where you can push your golden RTL and the spec modifications.

1. Fork the repo to your own GitHub account; Go to https://github.com/phinitylabs/takehome-stream-chunker and click **Fork**. Make sure the fork has **public** visibility. Remember to **uncheck** the `Copy the stream_chunker_baseline branch only` checkbox when creating the fork, so that all three branches are copied.
2. Clone the repo that you forked recently.

```bash
      git clone https://github.com/<your-github-username>/takehome-stream-chunker.git
      cd takehome-stream-chunker
```

post clone make sure you see all three branches

```bash
    git branch -a
    * stream_chunker_baseline
      remotes/origin/HEAD -> origin/stream_chunker_baseline
      remotes/origin/stream_chunker_baseline
      remotes/origin/stream_chunker_golden
      remotes/origin/stream_chunker_test
```

**Setup the framework repo (use Terminal 2):**

1. Clone the evaluation framework and install its dependencies:

```bash
    git clone https://github.com/phinitylabs/verilog-coding-template.git
    cd verilog-coding-template
    uv sync
```

Set your API keys. Your HUD API key can be created on [hud.ai](https://hud.ai) — go to your dashboard, then click "Phinity Labs" in the bottom left. Then click settings, this opens the project settings page, then go to the "API Keys" tab and create a new API key.

> **Note:** If you previously created an API key from the legacy HUD platform, that key will **not** work. Create a new key by following the above steps.

This framework uses **HUD v6**. Each problem runs in its own Docker image. The container serves a v6 control channel (`hud serve` on port 8765); the agent connects over SSH to edit files in the workspace. When the agent finishes, hidden tests grade the workspace via patch + pytest.

```bash
uv run hud set HUD_API_KEY=<your HUD key>
uv run hud set ANTHROPIC_API_KEY=<your Anthropic key from liaison>
```

> **Note:** if any `hud` command prints a banner suggesting you upgrade `hud-python`, ignore it — do not upgrade `hud-python`.

---



## Section 1: Understanding the Task (~30 min) (Terminal 1)

The task is a stream chunker: a valid/ready byte-stream module that segments
packets (delimited by `in_last`) into fragments of at most `MAX_PAYLOAD` = 4
payload beats, forwards payload beats with zero-latency combinational
passthrough, and inserts a two-beat trailer after each fragment — a length
byte, then a CRC-8 check byte XORed with an is-final seed (`out_last` marks
the final trailer beat). The agent receives:


| File                        | Purpose                                              |
| --------------------------- | ---------------------------------------------------- |
| `prompt.txt`                | High-level instructions telling the agent what to do |
| `docs/spec.md`              | Detailed specification of the chunker's behavior     |
| `sources/stream_chunker.sv` | Empty module skeleton — the agent must fill this in  |


The agent does **not** see the test or the golden solution. It reads the prompt and spec, writes SystemVerilog code, and can run its own tests. After it finishes, the hidden testbench grades its implementation.

### Branch structure

The repo has three important branches:


| Branch                    | What's on it                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `stream_chunker_baseline` | The starting point: empty skeleton + full spec. **This is what the agent sees.**                             |
| `stream_chunker_test`     | Same as baseline, plus the hidden cocotb testbench (`tests/test_stream_chunker.py`). Used for grading.       |
| `stream_chunker_golden`   | Same as baseline, but with the complete, correct implementation in `sources/stream_chunker.sv`. (To be implemented by you) |


To look at the hidden test:

```bash
git checkout stream_chunker_test
cat tests/test_stream_chunker.py
```

To return to the baseline (what the agent starts with):

```bash
git checkout stream_chunker_baseline
```

Take time to read `docs/spec.md` and `sources/stream_chunker.sv`. Understand what the stream chunker does — in particular the valid/ready handshake rules, the zero-latency passthrough obligation, when a fragment closes, the trailer byte formula, the per-fragment state lifecycle, and the reset behavior.

---

## Section 2: Creating the Golden RTL (~1-2 hr)

Based on the given specification file, create the Golden RTL in `sources/stream_chunker.sv` and push it on the `stream_chunker_golden` branch.

Make sure the RTL follows the specification file closely and fulfills every requirement.

In order to write and push your RTL follow the steps below:

```bash
git checkout stream_chunker_golden
# (implement sources/stream_chunker.sv per docs/spec.md)
git add sources/stream_chunker.sv
git commit -m "stream_chunker: golden implementation"
git push origin stream_chunker_golden
```

---

## Section 3: Running Tests Locally (~10 min)

You can run the hidden testbench locally to verify that the golden solution passes and the baseline fails.

First, checkout the test branch (which has the testbench):

```bash
git checkout stream_chunker_test
```

Run/execute the test against the **baseline** code using the command below (should fail — the skeleton ties its outputs low, so the testbench reports in_ready mismatches on the first cycles):

```bash
cd tests
uv run pytest test_stream_chunker.py --log-cli-level=INFO
```

You should see a failure. Now, temporarily swap in the golden solution and re-run:

```bash
cd ..
git fetch origin stream_chunker_golden
git checkout origin/stream_chunker_golden -- sources/stream_chunker.sv
rm -rf sim_build __pycache__ tests/__pycache__
cd tests
uv run pytest test_stream_chunker.py --log-cli-level=INFO
```

This should pass. Restore the baseline before continuing:

```bash
cd ..
git checkout origin/stream_chunker_test -- sources/stream_chunker.sv
```

---



## Section 4: Analyzing Agent Behavior (1 hour)

Here are the results of 10 runs of Claude Sonnet 4.5 attempting this task with the current spec:

**[View the 10 runs here](https://hud.ai/jobs/1f503c03e6bb45c4bebef93376dabd54)**

The agent achieves approximately **70% pass rate** — it solves the task correctly in most of the 10 attempts.

Open several **passing** runs (and any failing ones) and carefully read through the agent's work. Pay attention to:

- What approach does the agent take? What does it read first, and what does it copy nearly verbatim from the spec into its RTL?
- Does it test its own code? How does it build its reference model — and where does that model's correctness actually come from?
- Which parts of the spec does the agent lean on hardest? Which statements function as ready-made pseudocode?
- In the failing runs: what went wrong, and why didn't the agent's own tests catch it?

Understanding *how* the agent succeeds is the key to this takehome. The agent is not magically capable — there are specific, identifiable properties of the specification that let it converge on a correct implementation so reliably (and specific weaknesses in how it verifies itself). Your analysis of these properties will directly inform how you modify the spec. We strongly recommend working backwards — look at the final implementation the agent created at the end of the trace, and at the tests it wrote for itself, and compare both to the specification text. You can find the final implementation in HUD by scrolling to the bottom of the trace and looking through the code window in the final cell (on the left side of the transcript).

---



## Section 5: Modifying the Specification (~1–2 hrs)

Your goal is to modify `docs/spec.md` (and/or `prompt.txt`) so that the agent's pass rate drops to **between 10% and 50%** — while keeping the task fair.

**The fairness rules (hard constraints — submissions violating them are rejected):**

- The specification must remain **complete and unambiguous**: every behavior the hidden testbench grades must remain derivable from the spec text by a careful engineer. Removing required information, introducing contradictions, or wording that permits two readings where the testbench enforces one is not hardening — it is sabotage.
- Do not delete or weaken normative requirements the testbench checks.
- If you change what the module must *do* (a functional change), you must update the hidden testbench and your golden RTL consistently, and say so in your write-up.
- Your own golden RTL (Section 2) must still pass the hidden testbench after your changes.

**What you *may* do — make information harder to find and force derivation instead of transcription:**

- Replace operational, copy-paste-ready phrasing (step-by-step recipes, equation-form rules) with equivalent definitional phrasing that requires the reader to derive the algorithm.
- Remove statements that are implied by other statements (worked examples, restatements, emphasis, cross-references) so each fact appears exactly once, in its least prominent legal location.
- Strip redundancy between `prompt.txt` and the spec.
- Introduce additional, realistic protocol behavior (a **functional change**) whose corner cases require careful derivation — provided you update the hidden testbench and your golden RTL consistently and document the change. This is often necessary: presentation changes alone may not reach the band.
- Consider *how the agent verifies itself*: a change only lowers the pass rate durably if a wrong reading also corrupts the agent's own reference model the same way — otherwise its self-tests will catch and fix the mistake.

Principles to keep in mind:

- The agent is an AI model, not a human engineer. What makes a spec harder for a human may be absorbed effortlessly by an agent — and vice versa.
- The agent can look things up, write its own tests, and iterate. Removing information the agent can independently reconstruct (e.g., a standard algorithm identified by its parameters) is fair; removing information it cannot reconstruct is not.
- Each change should target a specific behavior you observed in the traces (Section 4). Blind deletions rarely move the number.

Each time you make a change, you should test it by running on HUD (Section 6).

---



## Section 6: Running on HUD (~30 min) (Terminal 2)

Now come to Terminal 2 for setting up the framework:

**Register the problem.** Open `src/hud_controller/problems/basic.py` and append:

```python
PROBLEM_REGISTRY.append(
    ProblemSpec(
        id="stream_chunker",
        description="""Implement the module `stream_chunker` in sources/stream_chunker.sv
according to docs/spec.md.

Requirements:
- Synthesizable SystemVerilog, compatible with Icarus Verilog (-g2012).
- No SystemVerilog Assertions (SVA).
- Keep the module name, parameter name and default, port names, directions,
  and widths exactly as in the provided skeleton. Grading uses the default
  MAX_PAYLOAD = 4.
- You may write and run your own tests, but grading is performed by a
  hidden testbench that checks cycle-exact behavior against docs/spec.md.

Deliverable: the completed sources/stream_chunker.sv. Do not modify any
other file.
""",
        difficulty="hard",
        base="stream_chunker_baseline",
        test="stream_chunker_test",
        golden="stream_chunker_golden",
        test_files=["tests/test_stream_chunker.py"],
    )
)
```

The branch names (`base`, `test`, `golden`) must exactly match the branches in your fork. Since forking preserves all branches, these already exist.

**Point the Dockerfile at your fork.** Open `Dockerfile` and find the `REPO_URL` line (near line 103):

```dockerfile
ARG REPO_URL=https://github.com/hud-evals/example-verilog-codebase.git
```

Change it to:

```dockerfile
ARG REPO_URL=https://github.com/<your-github-username>/takehome-stream-chunker.git
```

Since your fork is public, Docker can clone it without any authentication token.

### After each spec modification

**1. Update the branches.** From your forked repo (Terminal 1 `takehome-stream-chunker`), commit your spec change and push to all three branches — baseline, test and golden:

```bash
cd /path/to/takehome-stream-chunker
git checkout stream_chunker_baseline
# (make your spec edits to docs/spec.md)
git add docs/spec.md
git commit -m "modify spec"
git push origin stream_chunker_baseline

git checkout stream_chunker_test
git cherry-pick <commit-hash-from-above>
git push origin stream_chunker_test

git checkout stream_chunker_golden
git cherry-pick <commit-hash-from-above>
git push origin stream_chunker_golden
```

**2. Rebuild the Docker image.** Back in the (Terminal 2) framework repo, first increment the cache-buster in the `Dockerfile` so Docker pulls fresh code from your fork (find the `ENV random=random6` line near `REPO_URL` and change the number, e.g. `random7`, `random8`, etc.). Then build:

```bash
cd /path/to/verilog-coding-template
uv run utils/imagectl3.py verilog_ -b --ids stream_chunker
```

**3. Validate** (confirm golden passes, baseline fails):

```bash
uv run utils/imagectl3.py verilog_ -v --ids stream_chunker
```

**4. Generate tasks and run** (10 independent attempts):

```bash
uv run utils/imagectl3.py verilog_ -j --ids stream_chunker
```

This writes `tasks.py` with one row per problem. Then run the local eval driver:

```bash
uv run python run_eval.py --ids stream_chunker --agent claude --model claude-sonnet-4-5 --max-steps 100 --group-size 10
```

`run_eval.py` starts a fresh Docker container per rollout, runs the agent, grades each attempt, and prints progress plus a job URL like `https://hud.ai/jobs/<job-id>`. Open that link to inspect individual rollouts.

Iterate until you achieve a 10–50% pass rate.

---



## Section 7: Submission

Once you have achieved a pass rate between 10% and 50%, email your liaison with:

1. **Your Github Repo Link** with the final specification and golden RTL
2. **Your HUD results link** showing the pass rate
3. **A written analysis** containing:
  **A. Success Mechanism Analysis:**
   Pick 1 passing run from the [original 10-run evaluation](https://hud.ai/jobs/1f503c03e6bb45c4bebef93376dabd54). For that run, describe:
  - How the agent produced a correct implementation (its workflow, and which spec statements it relied on most directly)
  - How it verified itself (its own tests and reference model), and why that verification was able to converge on correctness
   **B. Vulnerability Analysis:**
   Where is the agent's process fragile? (e.g., which derivations does it get wrong without executable feedback? Which corners does it never test on its own? When do its reference model and its RTL share the same mistake?)
   **C. Spec Modifications:**
   What did you change in the spec and why? Connect each change to your analysis — explain the causal mechanism by which it lowers the pass rate (which agent behavior it defeats), and defend its fairness: show that the required behavior is still derivable from your modified spec, and that your own golden RTL still passes the hidden testbench.
   **D. New failure evidence:**
   Pick 1 run that fails against your modified spec and name the exact spec clause the agent's implementation now violates.

---

This takehome should take approximately **7–10 hours total**. The most important part is the analysis — we want to see that you can diagnose agent failures and reason about how to guide an AI model to produce correct hardware implementations.
