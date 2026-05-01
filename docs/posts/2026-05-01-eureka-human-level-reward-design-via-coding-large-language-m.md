---
title: "Eureka: Human-Level Reward Design via Coding Large Language Models"
date: 2026-05-01
authors:
  - RoboLens Bot
tags:
  - robotics
  - AI
categories:
  - Research Digest
description: >
  EUREKA is a novel reward design algorithm that leverages the zero-shot generation, code-writing, and in-context improvement capabilities of large language models to autonomously generate human-level reward functions for complex reinforcement learning tasks.
---

## TL;DR
EUREKA is a novel reward design algorithm that leverages the zero-shot generation, code-writing, and in-context improvement capabilities of large language models to autonomously generate human-level reward functions for complex reinforcement learning tasks.

## The Problem
Harnessing Large Language Models (LLMs) to learn complex low-level manipulation tasks remains an open problem. A critical bottleneck in applying RL to these domains is the design of effective reward functions. This process is notoriously difficult; 92% of polled RL researchers report relying on manual trial-and-error design, and 89% indicate that the rewards they design are sub-optimal.

Prior attempts to integrate LLMs into low-level manipulation suffer from significant constraints. Existing methods often necessitate substantial domain expertise to construct effective task prompts or are limited to learning only simple skills. Furthermore, prior work, such as L2R, relies on templated rewards, which lacks the expressivity necessary for complex tasks compared to EUREKA's free-form generation capability. Ultimately, manual reward engineering is tedious and frequently yields sub-optimal rewards, which can lead to undesirable or unintended behavior during RL training.

## Key Contributions
We present three primary contributions. First, EUREKA achieves human-level performance in reward design across a diverse suite of 29 open-sourced RL environments, encompassing 10 distinct robot morphologies. Specifically, it outperforms expert human rewards on 83% of these tasks, achieving an average normalized improvement of 52%. Second, EUREKA successfully solves dexterous manipulation tasks, such as pen spinning, for which manual reward engineering was previously infeasible, as demonstrated using a simulated Shadow Hand within a curriculum learning framework. Third, the framework enables a novel gradient-free in-context learning approach to Reinforcement Learning from Human Feedback (RLHF), allowing the generation of more performant and human-aligned reward functions based on various forms of human input without requiring any model updating.

## How It Works

![Figure 1: EUREKA generates human-level reward functions across diverse robots and tasks. Combined with
curriculum learning, EUREKA for the first time, unlocks rapid pen-spinning capabilities on an anthropomorphic
five-finger hand.](../assets/figures/2310.12931/fig_p1_0.png)
*Figure 1: EUREKA generates human-level reward functions across diverse robots and tasks. Combined with
curriculum learning, EUREKA for the first time, unlocks rapid pen-spinning capabilities on an anthropomorphic
five-finger hand.*

![Figure 2: EUREKA takes unmodified environment source code and language task description as context to
zero-shot generate executable reward functions from a coding LLM. Then, it iterates between reward sampling,
GPU-accelerated reward evaluation, and reward reflection to progressively improve its rew](../assets/figures/2310.12931/fig_p2_0.png)
*Figure 2: EUREKA takes unmodified environment source code and language task description as context to
zero-shot generate executable reward functions from a coding LLM. Then, it iterates between reward sampling,
GPU-accelerated reward evaluation, and reward reflection to progressively improve its rew*

![Figure 3: EUREKA can zero-shot generate executable rewards and then flexibly improve them with many distinct
types of free-form modification, such as (1) changing the hyperparameter of existing reward components, (2)
changing the functional form of existing reward components, and (3) introducing new](../assets/figures/2310.12931/fig_p4_0.png)
*Figure 3: EUREKA can zero-shot generate executable rewards and then flexibly improve them with many distinct
types of free-form modification, such as (1) changing the hyperparameter of existing reward components, (2)
changing the functional form of existing reward components, and (3) introducing new*

![Figure 4: EUREKA outperforms Human and L2R across all tasks. In particular, EUREKA realizes much greater
gains on high-dimensional dexterity environments.](../assets/figures/2310.12931/fig_p6_0.png)
*Figure 4: EUREKA outperforms Human and L2R across all tasks. In particular, EUREKA realizes much greater
gains on high-dimensional dexterity environments.*

EUREKA operates by treating the environment source code as direct context for a coding LLM (e.g., GPT-4). This allows for the zero-shot generation of executable reward functions. The core mechanism then employs an evolutionary search loop. In this loop, reward candidates are iteratively sampled from the LLM. The quality of these candidates is assessed via a mechanism called reward reflection, which summarizes the policy training dynamics into textual feedback. This reflection then guides in-context reward mutation, enabling the LLM to refine the best-performing reward function. The entire search process is accelerated by utilizing GPU-accelerated distributed reinforcement learning running on IsaacGym, which facilitates the extensive reward search required.

### Environment as Context
This component involves feeding the raw environment source code—excluding the existing reward code—directly into the LLM. This architectural choice enables the LLM to perform zero-shot generation of executable reward functions tailored to the specific dynamics and state space of the environment.

### Evolutionary Search
The system utilizes an iterative evolutionary search process. Independent reward candidates are sampled from the Coding LLM. Following evaluation, the best-performing candidate from the preceding iteration informs the next step via in-context reward mutation, driving the search toward higher-quality reward specifications.

### Reward Reflection
Reward Reflection serves as the automated feedback mechanism. It summarizes the policy training dynamics by tracking scalar values associated with all reward components and the overall task fitness function across intermediate policy checkpoints during training. This summary is then translated into textual feedback for the LLM.

### Coding LLM (e.g., GPT-4)
This is the foundational model responsible for the generation and mutation of the reward code. It utilizes the provided environment context and the textual guidance from Reward Reflection to produce refined, executable reward functions.

## Results
| Metric | Value | Baseline | Source |
| :--- | :--- | :--- | :--- |
| Outperformance on Isaac tasks | Exceeds or performs on par to human level | Human | Figure 4 |
| Outperformance on Dexterity tasks | Outperforms human level on 15 out of 20 tasks | Human | Figure 4 |
| Average normalized improvement | 52% | Human experts | Abstract |

## Why This Matters for Robotics
EUREKA demonstrates that LLMs can function as universal reward programming algorithms without necessitating task-specific prompting or the creation of rigid reward templates. Furthermore, the integration of evolutionary search with reward reflection proves crucial for mitigating the inherent sub-optimality associated with single-sample outputs from LLMs. Crucially, EUREKA establishes a gradient-free methodology to incorporate human feedback into the RLHF paradigm, circumventing the need for computationally expensive model updates. This shifts the paradigm from manual, expert-driven reward engineering to automated, LLM-guided reward discovery, which is essential for scaling RL to complex, real-world robotic tasks.

## Limitations & Open Questions
A primary limitation is that the initial reward generated by the LLM is not guaranteed to be executable or may exhibit significant sub-optimality. Additionally, empirical testing indicates that the performance of EUREKA degrades when GPT-4 is substituted with GPT-3.5, suggesting a strong reliance on the advanced coding capabilities of state-of-the-art LLMs. Future work must address the robustness of the initial generation phase and explore methods to stabilize the search process when the LLM output is highly divergent from executable code.
---

## Citation

```bibtex
@article{231012931,
  title   = {Eureka: Human-Level Reward Design via Coding Large Language Models},
  author  = {Yecheng Jason Ma and William Liang and Guanzhi Wang and De-An Huang and Osbert Bastani and Dinesh Jayaraman et al.},
  journal = {arXiv preprint arXiv:2310.12931},
  year    = {2023},
  url     = {https://arxiv.org/abs/2310.12931}
}
```
