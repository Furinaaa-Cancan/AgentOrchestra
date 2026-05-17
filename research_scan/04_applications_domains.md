# Applications & Domain LLMs — 2025–2026 Scan

Scope: code/SE, science, medicine, robotics, multimodal, real-world agents, knowledge work. Foundation models, reasoning, alignment, and efficiency are covered elsewhere.

---

## 1. Code Generation & SE Agents

Multi-agent SE pipelines are saturated (flag and skip). Frontier has moved to **repo-scale long-horizon** and **verified codegen**.

- **SWE-bench Pro / SWE-EVO** (2025–26) — long-horizon software evolution with multi-issue trajectories. [BenchLM leaderboard](https://benchlm.ai/coding)
- **Multi-SWE-bench** (ByteDance, 2025) — multilingual SWE-bench across Java/Go/Rust/JS, exposes English-Python overfit.
- **LiveCodeBench v6** (2025–26, 1055 contamination-free problems) — competitive coding eval. [livecodebench.github.io](https://livecodebench.github.io/)
- **RepoGenesis** (arXiv 2026) — 106 repos × 18 domains × 11 frameworks for end-to-end microservice generation from READMEs. [arxiv 2601.13943](https://arxiv.org/html/2601.13943)
- **VERINA / CLEVER / DafnyBench** (2025) — verified codegen in Lean/Dafny. SOTA ≈ 1/161 end-to-end; DafnyBench jumped 68%→96% (Opus-3 → GPT-5). [VERINA](https://arxiv.org/pdf/2505.23135), [CLEVER](https://arxiv.org/pdf/2505.13938), [DafnyBench](https://namin.seas.harvard.edu/pubs/dafnybench.pdf)
- **AlphaVerus** (CMU, 2025) — bootstrapped self-improvement loop for Verus-verified Rust. [paper](http://www.contrib.andrew.cmu.edu/~bparno/papers/alpha-verus.pdf)

Verdict: **HOT** = verified/formal codegen + long-horizon repo evolution. **SATURATED** = multi-agent issue-fix, HumanEval/MBPP. **EMERGING** = CI-loop agents (SWE-CI), multi-language repos.

Open questions:
- Can a single small prover (≤7B) close the Dafny↔Lean transfer gap, or does each FV target need a bespoke model?
- Does long-horizon SWE benefit more from *memory architecture* or *better localization*? Ablate one while fixing the other on SWE-EVO.
- Why does verified-codegen success collapse from spec-given to spec-also-generated? Single-axis controlled study.

---

## 2. Scientific LLMs (Math / Chem / Bio / Physics / Autonomous Discovery)

- **Goedel-Prover-V2** (Princeton, 2025) — open Lean-4 prover, 80× smaller than rivals, top open + competitive with closed. [arxiv 2508.03613](https://arxiv.org/pdf/2508.03613)
- **Aristotle** (Harmonic, 2025) — IMO-2025 gold-equivalent via Lean search + informal lemma generation + geometry solver. [paper](https://harmonic.fun/pdf/Aristotle_IMO_Level_Automated_Theorem_Proving.pdf)
- **Seed-Prover** (ByteDance, 2025) — formal IMO-2025 gold solutions.
- **AI-Researcher** (HKUDS, NeurIPS 2025 Spotlight) — fully autonomous research stack ideation→writeup. [GitHub](https://github.com/HKUDS/AI-Researcher)
- **AlphaFold 3** (DeepMind/Isomorphic, 2024–25) + **ESM-3** (EvolutionaryScale) + **Boltz-2** (MIT 2025) — joint structure + binding affinity; +50% over physics methods on PoseBusters. [comparison](https://intuitionlabs.ai/articles/biology-foundation-models-comparison)

Verdict: **HOT** = autoformalization + Lean RL, autonomous AI scientist loops. **EMERGING** = biomolecular dynamics, joint structure-affinity. **SATURATED** = MATH/GSM8K, single-protein structure prediction.

Open questions:
- Does informal-lemma scaffolding (Aristotle-style) help on *non-competition* math (textbook proof completion) or only contest geometry?
- Can AI-Researcher loops produce a *novel reproducible result* in a domain other than ML benchmark-tuning? Pre-register one bio/chem task.
- Are Boltz-2 binding-affinity gains real on **out-of-cluster** targets, or memorized from PDB neighbors?

---

## 3. Medical & Clinical

- **MedLM / Med-PaLM 2** lineage (Google, Nature Medicine 2025) — 86.5% MedQA. [Nature Med](https://www.nature.com/articles/s41591-024-03423-7)
- **CSEDB** (2025, npj Digital Medicine) — 2069 dual-track safety+effectiveness items, 26 departments; 6 LLMs averaged 57.2%, **13.3% drop in high-risk scenarios**. [paper](https://www.nature.com/articles/s41746-025-02277-8)
- **CliBench / CliMedBench / MedBench / LLMEval-Med** — EHR-grounded, real clinical-record benchmarks (the field's shift away from exam-MCQ).
- Systematic review of clinical LLM evals across PubMedQA/MedQA/MedMCQA: GPT-4 still beats specialist BioMed-LLMs on most tasks. [BMC MIDM 2025](https://link.springer.com/article/10.1186/s12911-025-02954-4)

Verdict: **HOT** = EHR-grounded, safety-stratified eval. **SATURATED** = MedQA/MMLU-clinical (saturating >90%). **EMERGING** = clinical agent workflows (tool-use, ordering).

Open questions:
- Does fine-tuning on medical corpora *still* help when base models exceed 90% on exam MCQ but fail high-risk CSEDB? One controlled FT-vs-prompt ablation.
- Are LLM diagnostic gains preserved under **distribution shift** (non-US guidelines, non-English histories)?

---

## 4. Robotics / Embodied AI (VLA)

- **π0 / π0.5 / π0.6** (Physical Intelligence, 2024–25) — flow-matching continuous-action VLA, 50Hz, open-sourced. [arxiv 2410.24164](https://arxiv.org/html/2410.24164v1)
- **OpenVLA** (Stanford 2024, baseline) — 7B, 970k demos, beats RT-2-X (55B) by 16.5%. [openvla.github.io](https://openvla.github.io/)
- **GR00T N1** (NVIDIA, Mar 2025) — humanoid dual-system VLA.
- **Gemini Robotics** (Google DM, 2025) — Gemini-2.0-based VLA extending multimodal to action.
- Systematic review of VLA for manipulation. [ScienceDirect 2025](https://www.sciencedirect.com/science/article/pii/S1566253525011248)

Verdict: **HOT** = generalist VLAs (π-family, GR00T, Gemini Robotics), dual-system System-1/System-2. **EMERGING** = humanoid whole-body, sim-to-real with diffusion policies. **SATURATED** = single-task imitation on RT-1-style benchmarks.

Open questions:
- Does dual-system (slow VLM planner + fast policy) actually beat monolithic flow-matching when matched on compute? Most papers don't control this.
- Cross-embodiment transfer: does π0-style data scaling buy *zero-shot* new-robot or just faster fine-tune?

---

## 5. Multimodal (Vision / Video / Audio / 3D)

- **Video-3D LLM** (CVPR 2025) — 3D position-aware video reps for scene QA. [arxiv 2412.00493](https://arxiv.org/abs/2412.00493)
- **TimeSuite** (ICLR 2025) — long-video instruction tuning with Temporal Grounded Captions.
- **Vid-LLM** (arxiv 2509.24385, 2025) — compact video→3D with reconstruction-reasoning synergy.
- **NVIDIA Canary-Qwen-2.5B** (2025) — first open Speech-Augmented LM, leads English ASR.
- **Mistral Voxtral** (Jul 2025) — 24B open speech LLM, 32K ctx, 30-min audio.
- **OpenAI gpt-4o-transcribe** (2025) — Whisper successor.

Verdict: **HOT** = long-video + spatial/3D grounding; speech-augmented LMs (SALMs). **EMERGING** = streaming video memory, omni-modal dialog (InteractiveOmni). **SATURATED** = short-clip VideoQA (MSR-VTT/MSVD).

Open questions:
- Do 3D position encodings (Video-3D LLM) help on **non-indoor** scenes (driving, outdoor), or is the gain ScanNet-specific?
- Is LLM-decoder ASR (Canary-Qwen, Voxtral) actually better than encoder-only Whisper-v3 *on disfluent real speech*, controlling for training data?

---

## 6. Real-World Agents (Computer-Use / Browser / OS)

- **OSWorld** (NeurIPS 2024) + **OSWorld-Verified** (Jul 2025) — 369 real cross-app tasks. [os-world.github.io](https://os-world.github.io/)
- **OSWorld-Human** (arxiv 2506.16042, 2025) — efficiency benchmark.
- **VideoWebArena** (ICLR 2025) — video-grounded web tasks. [paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/5b555804d495321df2e3208cc27f4fbc-Paper-Conference.pdf)
- Current state: GPT-5.4 75.0%, Opus 4.6 72.7%, human ≈72–84%. CUA jumped from 38% (Jan 25) → 75% (Mar 26). [Coasty 2026 ranking](https://coasty.ai/blog/osworld-benchmark-results-2026-who-actually-wins)

Verdict: **HOT and early** — closing on human baseline but not exceeding it; massive headroom in long-horizon, error-recovery, GUI grounding. **EMERGING** = OS-level (not just browser), enterprise back-office.

Open questions:
- What fraction of OSWorld gains come from **visual grounding** vs **planning**? Swap-in oracle screen parser to isolate.
- Do CUAs degrade more from *latency* or *accuracy* loss under real-world network/UI variance? OSWorld-Human suggests latency dominates.
- Is there a "recovery benchmark" — agents that mis-click and must self-correct — distinct from task success?

---

## 7. Knowledge Work & Education

- **FinanceBench** (10,231 SEC-derived Qs) — GPT-4-Turbo+RAG fails 81%; multi-agent RAG hits 56%. GPT-5 = 88.23% on financial reasoning. [aimultiple](https://aimultiple.com/finance-llm)
- **Legal tutoring ITS** (ResearchGate 2025) — LLM pedagogical agent for law courses. [link](https://www.researchgate.net/publication/396447632)
- Academic research assistants — DeepSeek-R1, Qwen3-30B-Thinking, GLM-4.5V dominate open-source. [SiliconFlow 2026](https://www.siliconflow.com/articles/en/best-LLMs-for-academic-research)

Verdict: **EMERGING** but commercially-driven, weak academic benchmarks. **SATURATED** = legal-MCQ (bar-exam-style). **HOT** = domain RAG + tool agents for finance/legal compliance.

Open questions:
- Is FinanceBench gap (19%→88%) real reasoning or longer-context-window? Strip context to fixed budget.
- Does Khan-style LLM tutoring produce **measurable learning gain** in randomized classroom studies, beyond user satisfaction?

---

## Top 5 Open Questions Across Slices

1. **Verified codegen at scale — does it transfer?** Verifier-augmented training (Lean/Dafny/Verus) shows huge gains on its own benchmark, but cross-formalism transfer is untested. *Min experiment*: train on DafnyBench, eval zero-shot on VERINA (Lean); compare to a model trained on Lean-only.

2. **Are autonomous AI-scientist loops producing novel-and-correct results, or novelty theater?** *Min experiment*: pre-register an AI-Researcher run on a held-out wet-lab/chem task with a human-graded novelty+correctness rubric.

3. **Is the CUA jump (38→75% in 14 months) GUI grounding or planning?** *Min experiment*: hold OSWorld fixed, swap (a) oracle DOM parser, (b) oracle plan; measure deltas — isolates the bottleneck.

4. **VLA dual-system vs monolithic, compute-controlled.** Every paper claims dual-system wins but mixes data/compute. *Min experiment*: train π0-style flat policy and a System-1/System-2 split with identical FLOPs and demos on LIBERO + a real robot.

5. **Do medical LLMs degrade gracefully under safety stress?** CSEDB shows 13.3% drop in high-risk. *Min experiment*: take 3 top med-LLMs, plot accuracy vs CSEDB risk-tier; fit a degradation curve and compare to a generic GPT-5 baseline — is specialization protective or fragile?

---

## Sources

- [LiveCodeBench](https://livecodebench.github.io/) · [BenchLM coding](https://benchlm.ai/coding) · [Awesome Repo-Level CodeGen](https://github.com/YerbaPage/Awesome-Repo-Level-Code-Generation)
- [VERINA](https://arxiv.org/pdf/2505.23135) · [CLEVER](https://arxiv.org/pdf/2505.13938) · [DafnyBench](https://namin.seas.harvard.edu/pubs/dafnybench.pdf) · [AlphaVerus](http://www.contrib.andrew.cmu.edu/~bparno/papers/alpha-verus.pdf)
- [Goedel-Prover-V2](https://arxiv.org/pdf/2508.03613) · [Aristotle](https://harmonic.fun/pdf/Aristotle_IMO_Level_Automated_Theorem_Proving.pdf) · [AI-Researcher (NeurIPS 2025)](https://neurips.cc/virtual/2025/poster/116385) · [AlphaFold 3 / ESM-3 / Boltz-2](https://intuitionlabs.ai/articles/biology-foundation-models-comparison)
- [Med-PaLM 2 (Nature Medicine)](https://www.nature.com/articles/s41591-024-03423-7) · [CSEDB (npj Digital Medicine)](https://www.nature.com/articles/s41746-025-02277-8) · [Clinical LLM systematic review](https://link.springer.com/article/10.1186/s12911-025-02954-4)
- [π0](https://arxiv.org/html/2410.24164v1) · [OpenVLA](https://openvla.github.io/) · [VLA systematic review](https://www.sciencedirect.com/science/article/pii/S1566253525011248)
- [Video-3D LLM](https://arxiv.org/abs/2412.00493) · [Vid-LLM](https://arxiv.org/html/2509.24385) · [VideoWebArena ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/file/5b555804d495321df2e3208cc27f4fbc-Paper-Conference.pdf) · [Voxtral](https://www.infoq.com/news/2025/07/mistral-voxtral-audio-speech-llm/) · [OpenAI next-gen audio](https://openai.com/index/introducing-our-next-generation-audio-models/)
- [OSWorld](https://os-world.github.io/) · [OSWorld-Human](https://arxiv.org/html/2506.16042v1) · [CUA explainer](https://www.marktechpost.com/2025/10/10/what-are-computer-use-agents-from-web-to-os-a-technical-explainer/) · [2026 leaderboard](https://coasty.ai/blog/osworld-benchmark-results-2026-who-actually-wins)
- [FinanceBench / finance LLM benchmark](https://aimultiple.com/finance-llm) · [Legal ITS](https://www.researchgate.net/publication/396447632) · [Research LLMs 2026](https://www.siliconflow.com/articles/en/best-LLMs-for-academic-research)
