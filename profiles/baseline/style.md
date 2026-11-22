# Baseline Style Guide

This is the paper-writer plugin's neutral default. It describes plain, precise technical
prose for systems and networking papers, not any particular author's voice. Replace it with
your own style profile for drafts that sound like you.

## 1. Voice and tone

- Confident and matter-of-fact. State what the system does and what the numbers show.
- No promotional language and no apology. Let results carry the weight.
- Use "we" for the authors' actions and decisions. Use the system's name as the agent of
  what the system does ("Acme reroutes flows", not "flows are rerouted by our system").

## 2. Sentences

- Vary length. Long sentences carry mechanisms; short sentences carry conclusions.
- Put the condition or cause first when explaining a mechanism ("Since X, Y").
- Prefer active voice. Use passive only when the actor is irrelevant.

## 3. Word choice

- Prefer the plain word: "use" over "utilize", "enable" over "facilitate", "new" over "novel".
- Keep one word per concept. Do not rotate synonyms for variety.
- Replace evaluative adjectives with numbers: "cuts tail latency by 38%", not "significantly
  reduces latency".

## 4. Hedging

- Hedge only real uncertainty, once, at the point where it applies.
- Avoid stacked hedges ("may potentially", "it could be argued that").

## 5. Transitions

- Use a small set of connectors and reuse them: "However", "Hence", "Note that",
  "In contrast", "This is because".
- Avoid filler transitions ("Moreover", "Additionally", "Needless to say").

## 6. Paragraphs

- Open with the claim. Develop it with evidence or mechanism. Close with a consequence or a
  pointer forward, not a restatement of the opening.

## 7. Section patterns

- **Introduction:** context, the problem and why it is hard, the key insight, the design in
  brief, results with numbers, and contributions.
- **Background and motivation:** the minimum the reader needs, then measurements or examples
  that show why existing approaches fall short.
- **Design:** one subsection per challenge, each stating the challenge, then the mechanism.
- **Evaluation:** the question each experiment answers, the setup, the result in numbers.

## 8. Argumentation

- Claim first, evidence immediately after.
- Name and cite prior work specifically. Do not allude to "existing approaches" without
  saying which ones and what property they lack.
- State limitations plainly and bound them.

## 9. Technical writing

- Define each term once, at first use, and keep using that term.
- Refer to figures and tables by number, and say what the reader should see in them.
- Cite findings directly ("A single migration takes 4 s [5]"), not by author name.

## 10. Anti-patterns

### Phrases to avoid

- "It is important to note that" (use "Note that")
- "delve", "landscape", "a wide range of"
- "plays a crucial role"
- "groundbreaking", "revolutionary", "cutting-edge", "unprecedented"
