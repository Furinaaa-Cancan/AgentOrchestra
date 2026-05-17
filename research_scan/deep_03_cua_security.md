# Deep Dive 03 — Computer-Use Agent Security: A Single-Researcher Opportunity

## 1. State of computer-use agents (2025–2026)

Capability on OSWorld has roughly doubled in 14 months. February 2025: Claude 3.7 led at ~28% pass@100 ([XLANG OSWorld-Verified blog](https://xlang.ai/blog/osworld-verified)). By April 2026 the OSWorld-Verified leaderboard shows Holo3-35B-A3B at 82.6%, Claude "Mythos" preview at 79.6%, Claude Opus 4.6 at 72.7% on the main leaderboard ([llm-stats OSWorld](https://llm-stats.com/benchmarks/osworld-verified)). Open-weights stack: ByteDance UI-TARS-1.5-7B and UI-TARS-2 ([arXiv 2509.02544](https://arxiv.org/abs/2509.02544)), OS-Atlas, ShowUI, Aria-UI; commercial-grounding leader Gelato ([mlfoundations/Gelato](https://github.com/mlfoundations/Gelato)). Shipped consumer products: Claude Computer Use (Oct 2024), OpenAI Operator (Jan 2025), ChatGPT Atlas browser agent (Oct 2025), Perplexity Comet.

## 2. Published attacks on computer-use / web / OS agents (2024–2026)

- **Pop-up attacks (visual UI injection).** Zhang, Yu, Yang, "Attacking Vision-Language Computer Agents via Pop-ups," ACL 2025 ([arXiv 2411.02391](https://arxiv.org/abs/2411.02391)). 86% click-through on adversarial pop-ups in OSWorld/VisualWebArena; 47% drop in task success. Ignore-instructions defenses fail.
- **Indirect prompt injection in browser agents.** Brave's disclosures against Perplexity Comet (white-on-white text, HTML comments, screenshot-embedded text in faint colors) caused cross-domain exfiltration including OTP retrieval ([Brave blog](https://brave.com/blog/unseeable-prompt-injections/)). Palo Alto Unit 42 documented in-the-wild web-page injections targeting agentic browsers ([Unit 42](https://unit42.paloaltonetworks.com/ai-agent-prompt-injection/)). OpenAI's own statement: Atlas prompt injection "may never be fully solved" ([TechCrunch 2025-12-22](https://techcrunch.com/2025/12/22/openai-says-ai-browsers-may-always-be-vulnerable-to-prompt-injection-attacks/)).
- **Adversarial perturbations on agent visual input.** Wu et al. and follow-ups show 67% targeted-hijack ASR by perturbing a single product image (<5% of page pixels, ε=16/255) against GPT-4o web agents. AdvEDM ([arXiv 2509.16645](https://arxiv.org/abs/2509.16645)) extends fine-grained object-level attacks to embodied/GUI VLMs. CVPR 2025 "Chain of Attack" benchmarks transferability across VLMs.
- **Backdoor attacks on MLLM GUI agents.** EMNLP 2025 Findings ([aclanthology.org/2025.findings-emnlp.411](https://aclanthology.org/2025.findings-emnlp.411.pdf)) — triggers embedded in screenshots cause targeted misclicks.
- **Framework-level RCE.** Microsoft's May 2026 disclosure: prompt-to-shell RCE in popular agent frameworks ([Microsoft Security Blog](https://www.microsoft.com/en-us/security/blog/2026/05/07/prompts-become-shells-rce-vulnerabilities-ai-agent-frameworks/)).

## 3. Indirect-prompt-injection benchmarks: state and gaps

- **AgentDojo** (Debenedetti et al., NeurIPS 2024 D&B) — 97 tasks, 629 attacks, tool-API setting. Best-agent ASR <25% but utility-under-attack drops from 69%→45% on GPT-4o; defenses (tool filter, secondary detector) trade utility for ASR ([arXiv 2406.13352](https://arxiv.org/abs/2406.13352)).
- **InjecAgent** (Zhan et al., ACL 2024 Findings) — 1,054 cases, ReAct-GPT-4 24% ASR, Llama2-70B >80% ([arXiv 2403.02691](https://arxiv.org/abs/2403.02691)).
- **WASP** (Evtimov et al., Meta, Apr 2025) — first end-to-end web-agent IPI benchmark targeting VisualWebArena + Claude Computer Use ([arXiv 2504.18575](https://arxiv.org/abs/2504.18575); [facebookresearch/wasp](https://github.com/facebookresearch/wasp)). Realistic hijack goals in sandboxed sites.
- **WAInjectBench** (Oct 2025, [arXiv 2510.01354](https://arxiv.org/pdf/2510.01354)) — focuses on *detector* evaluation, not agent robustness.
- **NIST ART benchmark + 2026 Agent Standards Initiative** ([NIST CAISI blog](https://www.nist.gov/blogs/caisi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition)). Their red-team competition reported 81% task-hijack success with novel attacks vs 11% baselines.

**Gap.** All published benchmarks target *web/tool* agents. None systematically covers full **OS-level computer-use** surfaces: native dialogs, OS notifications, file-system content, clipboard, screenshot OCR text, accessibility-tree tampering, and cross-app context bleed. WASP touches Claude Computer Use but only inside VisualWebArena pages.

## 4. Defenses and their known failures

- **System-prompt hardening / "ignore injections"** — broken by pop-up paper (86% ASR retained), Brave Comet attacks, NIST competition.
- **Secondary detector classifier** — AgentDojo cuts ASR to 8% but adds latency and brittle to OOD attacks; WAInjectBench shows detectors transfer poorly.
- **Tool filtering / capability gating** — strongest defense in AgentDojo (ASR 7.5%) but utility falls to 53%.
- **Action confirmation / human-in-the-loop** — defeated by social-engineering dialogs and confirmation-fatigue (NIST ART findings).
- **Adversarially fine-tuned models** (Atlas update, fine-tuned GPT-4 InjecAgent variant 3.8% ASR) — best so far but attack adaptation is fast and not publicly reproducible.
- **LaSM layer-wise scaling** (2025) — early architectural defense against pop-up attacks; not yet evaluated broadly.

Consensus from NCSC, OpenAI, Brave: IPI is a **systemic, possibly unsolvable** problem for vision-grounded autonomy.

## 5. Is there a rigorous CUA-security benchmark? — No.

WASP is the closest, but: (i) it is web-only, (ii) attacks are page-DOM injections not OS-level surfaces, (iii) it evaluates 2-3 systems. No published benchmark covers OS file managers, terminals, native dialogs, screenshot-text injection at OS scale, or open-weights UI-TARS/OS-Atlas under unified adversarial conditions. **That absence is itself the publishable artifact.**

## 6. Two concrete single-researcher paper proposals

### Proposal A (preferred) — "OS-Inject: A Benchmark for OS-Surface Prompt Injection on Computer-Use Agents"
NeurIPS D&B or USENIX Security target.

- **Setup.** Fork OSWorld VMs (already Dockerized). Add an injection layer that programmatically plants adversarial content in five OS surfaces:
  1. Desktop notifications / system toasts
  2. File names and file content the agent must read
  3. Clipboard contents
  4. Native confirmation dialogs (fake "OS update")
  5. Screenshot OCR text rendered as faint or in-image steganographic text
- **Attacks.** Port pop-up attack, Brave-style invisible text, AdvEDM-style ε=8/255 perturbations on icons, plus benign-looking social-engineering dialogs ("Your session will expire — click Continue").
- **Models.** Open-weights only required: UI-TARS-1.5-7B, UI-TARS-2, OS-Atlas-7B, ShowUI-2B, Aria-UI. Optional closed: Claude Sonnet 4.6 / Opus 4.6 via API, OpenAI Operator via Playwright bridge. Single A100 (80GB) or rented H100 hour suffices for open-weights; ~$2-4k API budget for closed-model rows.
- **Metrics.** Targeted ASR, untargeted derail rate, task utility under attack, attack stealth (would a human notice?), per-surface vulnerability heat-map.
- **Feasibility for a solo researcher.** All infra is open: OSWorld Docker, UI-TARS HF weights, WASP attack scaffolding reusable. Single-machine evaluation, ~2 months. No dedicated red-team org needed because all attacks are static templates, not RL.

### Proposal B — "Predictable Failures: A Scaling Law for VLM Agent Susceptibility to Adversarial Pop-ups"
ACL or IEEE S&P short paper.

- **Hypothesis.** Click-through ASR scales monotonically with (a) visual salience of the adversarial element and (b) inverse of grounding-head pretraining data overlap with that visual style. Predictable, model-independent.
- **Experiment.** Vary 6 pop-up dimensions (color contrast, area, z-order, mimicry of native OS chrome, text persuasiveness, position) factorially; measure ASR across UI-TARS-{1.5,2}, OS-Atlas, ShowUI, Aria-UI, Claude 4.6, GPT-4o-CUA. Fit a logistic-regression failure model; report cross-model R².
- **Why it's a paper.** If failure is predictable, defenders can *bound* risk; if not, the paper is the impossibility result. Either outcome publishable.
- **Cost.** ~$1k API, 1 GPU, 6 weeks. Strictly within solo capacity.

## Honest feasibility caveats

- Closed-model agent SDKs throttle screenshot input and can ban accounts during heavy adversarial probing — budget for two API keys and accept rate limits.
- OSWorld VMs are flaky; expect 10–15% run noise — solved by N≥5 seeds.
- Open-weights CUA grounding quality is much worse than Claude's; baseline utility may be too low to *measure* attack delta on hard tasks. Mitigation: subset to OSWorld tasks where the base model already exceeds 30% pass@1.
- WASP / AgentDojo / pop-up code are MIT/Apache — reusable. No new red-team infra required.

## Bottom line

The literature has fragmentary attack demos plus three web-centric benchmarks (AgentDojo, InjecAgent, WASP). **No one has published an OS-surface benchmark against the current top open-weights CUAs.** Proposal A fills that exact gap, is solo-feasible, and lands at NeurIPS D&B 2026 or USENIX Security 2027.
