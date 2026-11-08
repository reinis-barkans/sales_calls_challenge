# AI Engineer Coding Case: Sales Call Intelligence

## Overview

In this exercise, you will build a small AI-powered system for analysing sales call transcripts.

Imagine that a sales team records and transcribes its customer calls. Sales managers would like to ask questions across those calls and quickly understand what customers are saying, while being able to verify the system’s answers against the original conversations.

Your task is to build a simple working solution that allows a user to ask questions about a collection of sales call transcripts.

We expect you to spend **around 3–4 hours** on the exercise. Please do not spend significantly longer than this. We would rather see a focused solution with clear trade-offs than a highly polished or production-ready application.

You will present and discuss your solution in a follow-up interview.

---

## The task

Build a system that can answer questions based on the provided sales call transcripts.

The transcripts cover several kinds of call: prospect calls at various stages, renewal conversations with existing customers, churn post-mortems, and cold calls. Your system should handle questions that span these.

Example questions might include:

- What are the most common reasons prospects hesitate to buy?
- Which customers mentioned integrations with Salesforce?
- What concerns did customers raise about pricing?
- Which competitors were mentioned, and in what context?
- What product capabilities appear to be most important to prospects?
- What did Acme Corp say about their current workflow?
- Which prospects seem most likely to purchase, based on the conversations?
- Why did customers who left decide to leave?
- What is different about how the sales team handles renewals versus new business?
- Which cold calls produced a follow-up, and what did the successful ones have in common?
- Has anyone from the vendor given inconsistent answers about the product?

Your system should use the supplied transcripts as its source of truth.

A good answer should make it possible for the user to understand **where the information came from**, for example by returning supporting excerpts, transcript references, or another form of evidence.

You may implement the interface however you prefer. A command-line application, small API, notebook, or lightweight web interface are all acceptable. We care much more about the underlying approach than the presentation layer.

---

## Requirements

Your solution should:

### 1. Answer questions about the transcripts

Given a natural-language question, return a useful answer based on the available sales calls.

The system should support questions that may relate to:

- a single call;
- multiple calls;
- particular companies or prospects;
- themes that occur across the dataset.

You may choose whichever AI techniques you think are appropriate.

### 2. Provide evidence

Answers should include enough supporting information for the user to verify important claims against the source material.

For example, this might include:

- quotations or excerpts from calls;
- call or transcript identifiers;
- speaker information;
- links or references to relevant transcript sections.

The exact implementation is up to you.

### 3. Handle uncertainty

LLM-based systems can produce confident answers even when the available evidence is weak.

We would like your system to behave sensibly when:

- the transcripts do not contain the answer;
- the available evidence is ambiguous;
- different calls contain conflicting information.

You do not need to solve these problems perfectly. We are interested in how you think about them.

### 4. Include some evaluation

Create a small way of assessing whether your system is working.

This does not need to be a sophisticated evaluation framework. For example, you could:

- create a small set of representative questions and expected answers;
- test whether the correct source material is retrieved;
- evaluate whether answers contain the expected facts;
- test known failure cases;
- use an automated evaluator;
- combine automated checks with manual evaluation.

We are interested in both **what you choose to measure** and **why**.

---

## Provided materials

The starter repository contains:

- `calls/` — 20 fictional sales call transcripts as plain text;
- `manifest.json` — basic metadata for each call (company, industry, size, call type, stage, duration, participants);
- `README.md` — a short description of the dataset and the transcript file format;
- example questions (see above).

There is no starter application or project structure — the layout is yours to choose.

You may use external libraries, APIs, models, vector databases, or other tools where useful.

Please keep the solution reasonably easy for us to run locally.

---

## What to submit

Please send us your completed repository before the interview.

It should contain:

### Working code

We should be able to run your solution and ask it questions about the supplied transcripts.

Please include working basic setup and run instructions, in your `README.md`.

### Evaluation

Include the evaluation approach you created and, where practical, the results you observed.

Please include working instructions for setting up and running the evaluation, in your `README.md`.

### README

Please include a short README covering:

**Approach**

Briefly describe how your solution works.

**Key decisions**

Explain the most important technical choices you made.

**Assumptions**

Call out any assumptions you made about the data, users, or expected behaviour.

**Known limitations**

Describe situations where you expect the system to perform poorly.

**With more time**

Describe what you would improve if you had another day and what you would change if you were taking the system to production.

We do not expect a lengthy design document. Concise notes are sufficient.

**Setup and Run instructions**

For both the code and the evaluation.

---

## What we are not looking for

You do **not** need to:

- build a polished frontend;
- deploy the application;
- build production authentication or infrastructure;
- support large-scale traffic;
- optimise every aspect of latency or cost;
- create a perfect general-purpose sales analysis product.

Please prioritise the parts of the problem that you believe are most important.

Using AI coding assistants is **strongly encouraged**. Please be prepared to explain the submitted code and the decisions behind it.

---

## Timebox

Please spend approximately **3–4 hours** on the exercise.

This is intentionally not enough time to build everything you might want.

Part of the exercise is deciding:

- what to prioritise;
- what to simplify;
- what to leave unfinished;
- how to identify whether your approach is actually working.

If you reach the time limit with things you would still like to improve, document them in the README rather than continuing indefinitely.

---

# Follow-up interview

In the interview, we will spend approximately **60 minutes** discussing your submission.

You should be prepared to give a short walkthrough of your solution, including:

- how the system works;
- the main decisions you made;
- what worked well;
- what did not work as well as you hoped.

We will then explore the solution together.

This may include discussing:

- examples where the system produces a poor answer;
- how you would diagnose and improve those failures;
- alternative technical approaches;
- evaluation strategies;
- latency and cost;
- handling a much larger number of calls;
- incorporating new calls continuously;
- security and privacy considerations;
- what would be required to make the system production-ready.

We may also introduce a new product requirement and ask you to talk through how you would adapt your solution.

There is no expectation that you modify or complete significant amounts of code during the interview.

---

## What we care about

There is no single correct architecture for this exercise.

We are primarily interested in:

- **Problem solving:** how you break down an ambiguous AI problem.
- **AI engineering:** whether you choose appropriate techniques and understand their trade-offs.
- **Evaluation:** how you determine whether the system is actually performing well.
- **Reliability:** how you think about grounding, uncertainty and failure cases.
- **Software engineering:** whether your solution is understandable and maintainable.
- **Communication:** whether you can clearly explain your decisions and identify alternatives.

A simple solution that is well-tested and well-understood is preferable to a fancy solution that is difficult to evaluate or explain.
