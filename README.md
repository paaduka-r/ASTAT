Goal:
## Project Overview: The ASTAT Benchmark
I have been using AI tools for more than a year now, and seen them improve rapidly every month. But, the issues of hallucination continue to fester. As much as tremendous advances are being made in super hard problems from playing Go and protein folding to competitive exams like International Math Olympiad (IMO) and International Collegiate Programming Contest (ICPC), there are still many ways in which the latest and greatest LLMs are not smarter than what I experience as a 12th grader.
Inspired by LMArena and LLM-Stats, I have created and curated a set of 50 problems to be able to compare the latest models of ChatGPT, Gemini, Claude, and Grok. The aim of this project is to rigorously expose and categorize the specific types of hallucinations and reasoning failures these models exhibit when pushed beyond their standard training data.

### The ASTAT Dataset

The benchmark consists of 50 manually curated, original problems grounded in strict 12th-grade academic standards. To prevent models from simply regurgitating memorized answers, these problems are not scraped from public exams. 

The dataset is multidisciplinary by design. It includes complex STEM questions that feature multi-step logic and floating-point math traps, alongside highly structured humanities questions (such as the theoretical rules of Carnatic music and Bharatanatyam). This blend forces the models out of their comfort zones, making it highly likely they will attempt to invent plausible-sounding but entirely incorrect rules when they lack domain-specific knowledge.

### Testing Methodology

To ensure scientifically valid and reproducible results, all models will be tested under strictly controlled conditions. 

* **Strict Zero-Shot Prompting:** The models will receive only the raw problem statement, exactly as it would appear on a high school exam. They will not be given any system prompts instructing them to "think step-by-step" or "show their work." This tests their pure, out-of-the-box reasoning.
* **Controlled Environment:** Models will be queried either via their official APIs or in clean, fresh web-interface sessions with no prior chat history to prevent context contamination.
* **Maximum Determinism:** If using APIs, the temperature will be set to 0.0 to force the most factual, highest-probability output and eliminate creative variance.

### Expected Deliverables and Grading Criteria

The final result of this project will be a comprehensively formatted document (or spreadsheet) containing the problem, the golden "ground truth" answer, the exact output from each model, and a specific error classification. 

Because LLMs often naturally output explanatory text even when not asked to, grading will not be a simple binary Pass/Fail. Every response will be manually categorized into one of the following classifications:

* **Pass:** The model outputs the correct final answer, and any unprompted explanation it provides is logically sound.
* **False Positive:** The model arrives at the correct final answer, but reading its unprompted explanation reveals that it used coincidental, hallucinated, or mathematically invalid steps to get there. This is counted as a failure of reasoning.
* **Silent Failure:** The model outputs an incorrect final answer (such as a simple calculation or floating-point error) without providing enough explanatory text to determine exactly where its logic broke down.
* **Verifiable Hallucination:** The model outputs an incorrect answer and naturally provides an explanation that includes completely invented facts, fake theorems, or irrelevant logic to justify its mistake.
* **Refusal:** The model falsely claims it cannot answer the question due to safety filters or a stated lack of capability.
