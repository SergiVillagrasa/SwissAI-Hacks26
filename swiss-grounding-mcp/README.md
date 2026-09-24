# Swiss Grounding MCP

Swisscom myAI challenge at the Swiss AI Weeks Zurich hackathon, 24. and 25. September 2026, Kraftwerk, Selnaustrasse 25, Zurich.

Large language models can search the web, but they still struggle to answer questions about Switzerland reliably. Useful public information is spread across federal, cantonal, municipal and institutional sources in several languages, and generic search often returns the wrong jurisdiction, an outdated page or a source from a neighbouring country. Your task: build an MCP server that makes authoritative public Swiss information accessible to AI assistants, so that Swisscom can connect it to a standard MCP client and test it during the hackathon. The full challenge description is on the [Swiss AI Weeks challenge page](https://ai-weeks.ch/2026/challenges) (filter Zurich Hackathon) and in the Hacker's Handbook.

## In this folder

- [Agent guide](AGENTS.md): guidance scoped to this challenge folder.
- [Briefing deck](briefing-swiss-grounding-mcp.pdf): the slides from the virtual hacker Q&A on 16. September 2026, updated on 21. September 2026 with the answers below.
- This README: the answers to the questions you asked in the Q&A, the topic areas we draw test questions from, sample questions, and what you deliver.
- [Submission self-check pack](#submission-self-check-pack): practice cases and an evidence checklist for reviewing your submission against the published judging priorities.

## Your questions from the Q&A, answered

### 1. What will be tested, and how is different coverage compared fairly?

**Declare your scope.** In your README, state which topics and which geography your server covers, for example "waste collection and school holidays for all municipalities in the canton of Bern" or "federal tax and health insurance information for all of Switzerland". We evaluate answer quality against that declaration. The breadth of your coverage is evaluated and weighted separately. In general, a high quality solution with narrow coverage is preferred over a broad solution with low quality. Having both is best and wins.

**Three views on every server.**

- Answer quality inside your declared scope: correct, from an authoritative Swiss source, right jurisdiction, current, and cited.
- Breadth: how much useful public Swiss information your server makes accessible.
- Honesty outside your scope: a few questions will fall outside what you declared. The right behaviour is to say clearly that this is not covered, not to guess.

**Asking back can be the right answer.** When the answer depends on information that is missing, such as the municipality, a precise request for exactly that information counts as correct. When the question can be answered as asked, asking back counts as wrong, and so does asking for context you do not need.

Before your final demo, use the [submission self-check pack](#submission-self-check-pack)
to check citation support, jurisdiction, missing context and honest failure handling.

**What we tell you in advance, and what we keep.** This repository lists the topic areas we draw questions from and around five sample questions, including one where the correct response is to ask for the municipality. The full question set stays hidden, and we do not publish its size. Questions come in the four national languages: German, French, Italian and Romansh.

**How we test.** Every team is tested with the same setup: two different MCP compatible clients, each run with two different LLMs, so four combinations in total, connected to your server exactly as your setup instructions describe. We do not disclose which clients and which models we use, so build against the MCP standard rather than against one specific assistant. Automated checks and LLM assisted comparison against verified answers inform the Swisscom myAI review group, which makes the final assessment by hand. There is no published formula. The order of importance is: correct and honest answers, then breadth, then agent efficiency, operability and the quality of your MCP contract as tie breakers.

### 2. Which sources should we use, and will Swisscom provide a list?

Choosing and reaching the right sources is part of the challenge. Swisscom does not prescribe a source list, and the evaluation does not check whether you used specific sites. It checks whether your MCP server reaches authoritative Swiss information and returns useful, grounded answers with references people can verify. You may curate a source registry, discover sources dynamically, query open data and APIs, or combine approaches.

**What counts as authoritative.** The body that is actually responsible for the matter: the federal office, the canton, the municipality, or an organisation with a legal mandate. A few rules of thumb for recognising authority in Switzerland:

- Federal offices publish under admin.ch. ch.ch is the Confederation's multilingual citizen portal and a good map of who is responsible for what.
- Cantons publish under their own domains, usually the two letter canton code, for example be.ch, vd.ch, ti.ch, gr.ch.
- Municipalities publish on their own websites. Many local answers, such as waste collection, registration, or local fees, exist only there.
- Some semi official bodies are authoritative because the law gives them the job, for example the AHV/IV information centre or the public transport open data platform.
- Switzerland has four national languages. A source may exist in only one or two of them, and the correct answer may depend on the language region.

**Respecting robots.txt and terms of use must be configurable.** Your server should respect the robots.txt and terms of use of the sources it accesses by default. Whether it does so must be a configuration setting, not hardcoded behaviour, so that Swisscom can switch it on or off when running your server for testing. Document the setting and its default in your README.

**Example topic areas and sources.** These illustrate the range of questions people ask about Switzerland and where authoritative answers live. They are examples, not a required list, and not the evaluation set. You do not have to cover all of them; a focused, well grounded solution is valid.

| # | Topic area | Typical question | Example authoritative source | Level |
| --- | --- | --- | --- | --- |
| 1 | Health insurance premiums and basic insurance | "What is the cheapest basic insurance premium for me?" | `priminfo.admin.ch` | Federal (BAG) |
| 2 | Taxes and fees | "How much cantonal tax do I pay on this income?" | Ticino tax administration, `ti.ch` | Cantonal |
| 3 | Law and regulations | "What does the law say about notice periods?" | `fedlex.admin.ch` | Federal |
| 4 | Waste collection and recycling | "When is cardboard collected where I live?" | City of Lausanne waste calendar, `lausanne.ch` | Municipal |
| 5 | Moving, residence registration and civil status | "How do I register after moving?" | City of Bern residents' office, `bern.ch` | Municipal |
| 6 | Residence permits and migration | "Which permit do I need to work here?" | `sem.admin.ch` | Federal |
| 7 | Social insurance and pensions | "How is my AHV pension calculated?" | `ahv-iv.ch` | Semi official |
| 8 | Work and unemployment | "How do I register as unemployed?" | `arbeit.swiss` | Federal (SECO) |
| 9 | Schools and education | "When are the school holidays?" | Geneva education department, `ge.ch` | Cantonal |
| 10 | Public transport and mobility | "What is the next connection to Bellinzona?" | `opentransportdata.swiss` | Semi official (BAV mandate) |
| 11 | Road traffic, vehicles and driving licences | "How do I convert my foreign driving licence?" | Graubünden road traffic office, `gr.ch` | Cantonal |
| 12 | Housing and renting | "What is the current reference interest rate?" | `bwo.admin.ch` | Federal |
| 13 | Voting, elections and political rights | "What is being voted on next?" | `bk.admin.ch` | Federal |
| 14 | Companies, commercial register and VAT | "Is this company registered?" | `zefix.ch` | Federal |
| 15 | Customs and ordering from abroad | "What do I pay when I import a parcel?" | `bazg.admin.ch` | Federal |
| 16 | Statistics, open data, geodata and weather | "How many people live in my municipality?" | `bfs.admin.ch`, with `opendata.swiss`, `map.geo.admin.ch` and `meteoswiss.admin.ch` as cross topic portals | Federal |

### Sample questions

**Five sample questions.** They show the kind of questions in the hidden set, not its content. One of them can only be answered after asking which municipality is meant. One of them is not a question about Switzerland at all, and the right response is to say so. We do not tell you which.

1. Wann wird bei uns das nächste Mal Karton abgeholt?
2. Comment puis-je échanger mon permis de conduire étranger contre un permis suisse dans le canton de Vaud, et combien de temps ai-je pour le faire?
3. Qual è il premio mensile più basso dell'assicurazione di base per un adulto di 30 anni domiciliato a Lugano con franchigia di 2500 franchi?
4. Cura èn las vacanzas d'atun 2026 per la scola da Scuol?
5. Wie hoch ist der Rundfunkbeitrag, den ich nach meinem Umzug nach Konstanz zahlen muss?

### Submission self-check pack

**Want a stronger submission? Check the cases that a polished demo can miss.**
The companion pack turns the published judging priorities into practice cases:
citations that actually support a claim, the right municipality and reference year,
asking only for essential missing context, and honest responses when retrieval fails.
It also includes an evidence checklist to use before your final demo.

The companion utility reads a pinned snapshot from Git history without restoring
files into your working tree. From the repository root, print the report with:

```sh
python3 -c 'import subprocess,sys; exec(subprocess.check_output(["git","show",sys.argv[1]+":swiss-grounding-mcp/evaluation/launch.py"]))' \
  0fc28ee6540800833e43406fc935c28e569c0d3c --dry-run
```

Run its automated checks with:

```sh
python3 -c 'import subprocess,sys; exec(subprocess.check_output(["git","show",sys.argv[1]+":swiss-grounding-mcp/evaluation/launch.py"]))' \
  0fc28ee6540800833e43406fc935c28e569c0d3c --check
```

Python 3.8+ and Git are required; no packages or credentials are needed. Use a
clone with full history. For an existing shallow clone, fetch the history with
`git fetch --unshallow` before running the utility. The launcher does not fetch
automatically. Session setup is described in the root agent guide.

These practice cases target the published criteria; they are not hidden evaluation
questions or a scoring formula.

### 3. How must the solution run, and what support is available for embeddings and costs?

**Run it locally or hosted, your choice.** We can test your server as a hosted endpoint or by starting it ourselves from your repository. Either way, the code in your repository must also run locally with the setup you document, so that we can confirm that the published source is the server we tested. If you host it, keep the endpoint up until the evaluation is complete.

**Prebuilt indexes and embeddings are fine.** You do not have to embed or crawl everything at start time. You may ship a prebuilt vector store or index with your repository, or have your setup download it from a location you provide. Two conditions: the setup must fetch and use it without manual steps, and the repository must contain the script that built it, so that anyone can rebuild it later with fresher data. We do not rebuild your index during the evaluation.

**Keys and test access.** If your server needs API keys or other credentials at runtime, for example for query time embeddings or an LLM call inside the server, that is acceptable. List every required credential in your README, and hand working test credentials to Swisscom through the organisers' secure channel before the submission deadline. Never commit secrets to the repository. A server that runs without any external keys is easier for us to run and easier for you to keep running, and that shows in the operability assessment.

**Costs and credits.** Swisscom does not reimburse API, embedding or hosting costs. In the Q&A, the Swiss AI Weeks organisers mentioned API credits for participants. Ask them directly, and we will add any confirmed details to this page. Embedding budget does not decide the ranking: quality inside your declared scope comes first, and a small, well built index or a live API approach with no embeddings at all is just as valid as a large vector store.

## What you deliver

- A GitHub repository, public or private, with access for the Swisscom evaluators.
- A working MCP server with clear setup instructions, so that we can run it ourselves.
- Documented coverage and limitations: which topics and which geography you cover.
- Secure test access where needed, and no secrets in the repository.
- No myAI integration is needed during the event.

## Support during the hackathon

Swisscom myAI experts are on site at Kraftwerk with bookable 15 minute slots on Thursday afternoon and Friday morning. For questions before the event, reach us through the Swiss AI Weeks organisers.

Matthias Appius and Alexander Stark, Swisscom myAI

## Updates

- 21. September 2026: presentation and Q&A answers published.
