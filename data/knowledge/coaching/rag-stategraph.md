---
id: rag-stategraph
title: "RAG as a state graph: how a football answer stays grounded"
category: coaching
tags: [stategraph, rag, retrieval, grading, citations, refusal, answer-cache]
applies_to: [all]
difficulty: advanced
source: "FOOTBALL OS original editorial content — written for this project, no external text reproduced"
confidence: high
last_reviewed: 2026-11-17
---

## "how do I know the answer I get back is from the corpus, not invented"

Every question asked of a knowledge base travels the same road, and it is a better question to ask about the road than about the answer. A serious retrieval pipeline is not a lookup and it is not a long prompt — it is a small machine: a shared state that accumulates what was asked, what was found, what was checked and what was refused, and a fixed set of steps that each read that state and hand back an update to it. If you have read the StateGraph page, this is the same three parts — state, nodes, edges — applied to a job that has to ground every sentence in something retrievable.

## The pipeline, node by node

The journey of one question is a walk through the graph. A classify node reads the raw question and writes into the state what kind of work it needs — a definition, a protocol, a match decision, a rules clarification — and the routing edge reads that field to pick the next step. A retrieve node runs hybrid search — a keyword pass for words that must appear ("handball", "zonal") and a vector pass for words that mean the same thing — and appends the candidate chunks. A coverage edge then grades them: enough text from enough distinct documents to answer well, weak candidates refused here before any answer is written. A compose node builds the reply strictly from the surviving chunks and cites each sentence back to its chunk; a citation node checks those citations resolve; a refusal node catches what the pipeline declined and says so plainly. Each node is small, typed and pure; the graph is the orchestration.

## Why the loop is bounded, not hopeful

Between grading and composing sits the one place a retrieval graph can spin: a weak first pass that a system wants to retry forever. A bounded graph sets a budget at compile time — one re-retrieve with a widened query is a healthy loop, the difference between improving its answer and burning its allocation proving the same point three times. Every cycle needs a hard bound set where the graph is compiled, not a judgement made in the moment. A question that cannot be grounded after its budget is an honest refusal, and the graph routes it there.

## What the state carries that a chain cannot

A chain forgets the middle; a state object does not. By the time the compose node runs, the state knows: the question, the normalised form of it, which documents were asked, which chunks survived, what the coverage score was, which citation check failed if one did, and how many attempts this question has consumed. That makes audit possible — "why did the graph answer this" is answered by reading the saved state, not by trusting the final text — and it makes the run resumable, because a checkpointed thread identifier reopens the same work at the same node with the same bytes. The answer cache sits at the boundary of that graph: a repeat of the same question returns the saved result without re-walking the nodes, and the ledger counting those hits is part of the same graph, not an afterthought around it.

## Grading before writing is the whole discipline

The most important edge in the graph is the one that decides whether the composer is allowed to speak. Retrieval quality is bidirectional: a confident answer built on weak chunks is worse than a refusal, because the reader cannot see the difference from outside. A grading node that scores coverage — how much of the question the surviving text actually supports, and from how many independent documents — turns "the model sounded sure" into "the corpus said so, and here is the passage". The refusal is not a failure branch; it is a first-class route with its own node, its own copy and its own audit line, and it is the route this project uses when the coverage edge says the corpus does not know.

## Evidence and its limits

This page describes the design pattern this product ships in its knowledge ask flow — heading-anchored chunking, hybrid keyword and vector search, a coverage floor before composing, citation integrity checks on every sentence, an answer cache keyed on the question, refusals that fire instead of guesses. The framing of nodes and edges is the same pattern described in the project's StateGraph page applied to retrieval specifically. What is *not* claimed: that every retrieval system must use this shape, that a larger graph is a better one, or that grading eliminates hallucination entirely — it removes the *unearned* assertion, not the possibility of a confident mistake inside a passage that genuinely but wrongly supports it. Typical deployments that skip the coverage edge are the failure mode this design exists to prevent.

## When this does not apply

A single static lookup — a fixture, a rulebook excerpt, a club directory — is a read, not a question, and needs no graph; wrapping it in nodes and edges adds ceremony without legibility. Retrieval over a corpus with no refusal route is a worse place to start than plain keyword search, because the missing grading node is exactly what turns weak matches into confident prose. And a question about tomorrow's line-up, a live injury, or a figure no snapshot carries cannot be answered from any corpus — a graph that loops on those is a budget being spent, not a question being studied; the honest edge routes to refusal, and it should fire long before the budget is gone.
