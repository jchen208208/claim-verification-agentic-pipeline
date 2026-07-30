# Working state

Fast changing information only. For anything stable, including the architecture, the build order, the schedule, the data schema, and the related work, see the architecture plan.

Last updated: end of week 1.

---

## Where the project stands

Week 1 is done. The repository is cloned, the data structure is confirmed, both local models are installed and benchmarked on a real example, and the visual build plan has been sent to my professor. A meeting is scheduled for Wednesday morning Beijing time, which is Tuesday evening Pacific.

Nothing has been built yet beyond a throwaway script for constructing test prompts. The next real task is the harness described as stage 0a in the plan.

## Machine and environment

The work machine is a 2017 Intel MacBook Pro running macOS 13 Ventura, with 16 GB RAM. There is no usable GPU for inference, so everything runs on CPU.

Ollama is pinned at version 0.12.3. This matters: version 0.12.4 dropped support for macOS 12 and 13, and this Mac cannot upgrade past Ventura because 2017 hardware is not supported by later macOS releases. Automatic updates must stay off or the whole local setup breaks.

Models pulled locally:

    qwen2.5-coder:3b        the main working model
    qwen2.5-coder:7b        kept for quality comparison, too slow for batch runs
    nomic-embed-text        for the search step, not yet used

## Things that cost time and should not be rediscovered

Ollama defaults to a 4096 token context window and truncates anything longer without warning, without an error, and without any sign in the output. A realistic prompt for this benchmark runs close to 4000 tokens, so the default silently clips real evidence. Every run needs the window set explicitly, either with `/set parameter num_ctx 8192` in an interactive session or by passing `num_ctx` in the API options. Interactive settings do not persist between sessions.

Each element of a report's `context` array is a dictionary with `id` and `context` keys, not a plain string. A loader that assumes strings will silently produce garbage rather than failing loudly. This caused the week 1 benchmarking failure.

The examples in the dataset are grouped by answer in solid blocks, and the direction changes between subsets. In testmini, ie and numeric put the false claims first, but knowledge puts the true ones first. Any sampling that does not shuffle or stratify will produce a wildly misleading result.

The dataset is bigger than the paper says. Testmini holds 700 examples, not 600, and test holds 1,700, not 1,500. The test file also ships with real labels, so the whole "labels are withheld" assumption in the plan is wrong. Counted directly from the files on 29 July. See section 2.6 of the architecture plan.

The numeric subset spells the explanation field `explaination`. The other two subsets spell it correctly. Handle both.

## Currently blocked on

Cloud API keys from my professor, for DeepSeek and Qwen. Nothing involving the cloud half of the architecture can start without them. For Qwen specifically I also need to know which Alibaba Cloud region the account belongs to, because keys are not interchangeable between regions and the wrong endpoint returns a 401.

## Still outstanding from week 1

Checking the FINDVER leaderboard for recent submissions, and running a citation search for papers published since the benchmark. Both are needed before repeating any claim that nobody has attempted something. Neither has been done yet.

## Measured performance, for planning purposes

On a roughly 4000 token prompt, the 3B model takes about four minutes forty five seconds end to end and the 7B model takes about eleven minutes forty five. Memory use peaked at 2.5 GB and 5 GB respectively, so RAM is not the constraint. CPU speed is.

That works out to roughly eight hours for a hundred examples on the 3B model, or about fifty five hours for the full seven hundred example development set. Any plan involving repeated full runs needs to account for that.
