# Labeling rules

Every labeled posting has 7 fields. Label ONLY what the post actually says. Never guess.

## General
- Several jobs in one post → label the FIRST role only (the first role in the post's top line / header)
- Header and body disagree → use the more specific statement
- Not a job ad at all (a person looking for work, junk like ".") → skills blank, everything else unknown/blank
- Not a normal job (PhD, fellowship) → still label what's stated

## seniority
One of: `intern`, `junior`, `mid`, `senior`, `lead`, `unknown`
- "Sr." / "Senior" → `senior`
- "Staff", "Principal", "Head of", "Lead", "CTO" → `lead`
- "Early-career", "junior engineers welcome" → `junior`
- Two or more levels ("Staff/Senior", "Mid-to-Senior") → the FIRST one written
- "All levels welcome" → `unknown`
- No level stated → `unknown` (years of experience alone don't count)

## remote
One of: `remote`, `hybrid`, `onsite`, `unknown`
- Remote as an OPTION for the whole job ("NYC or Remote", "remote considered") → `remote`
- A MIX of office and home ("onsite + part remote", "3 days in office") → `hybrid`
- Says "ONSITE", "in person", "in office" → `onsite`
- Any Remotive posting → `remote` (Remotive only lists remote jobs)
- Only a city, no word about how you work → `unknown`

## salary_min / salary_max
- Plain whole numbers: "170k" → `170000`
- One number only ("$14/hour", "$80k") → same number in both
- "X+" ("110k+") → salary_min X, salary_max blank
- Text and a "Salary:" line disagree → use the "Salary:" line
- "+ equity", "+ bonus", "+ stock options" → ignore, base salary only
- No salary stated (or "competitive", or equity only) → `null` in both

## currency
- 3-letter code: `USD`, `EUR`, `GBP`...
- "$" with no country → `USD`
- No symbol, but the post clearly names the country → that country's currency (London, UK → `GBP`)
- No salary → `null`

## salary_period
One of: `hour`, `month`, `year`, `unknown`
- "/hour", "/hr" → `hour`; "/month" → `month`
- "k" or a full yearly-size number ("$175,000") with no other hint → `year`
- Paid per task, per word, per project → `unknown`
- No salary → `null` (even if the post says "hourly")

## skills
- Technical skills only: languages, tools, frameworks, cloud, named hardware/protocols (python, aws, docker, fpga, uart...)
- Not soft skills or general areas: no "communication", "english", "seo", "full-stack", "ai tooling", "databases"
- Include "nice-to-have" skills too, and "X or Y" means include all of them
- Include the team's tech stack when the post lists it
- Ignore lists of OTHER roles or other stacks ("not your stack?", "we also hire...")
- Ignore tech that describes the company's PRODUCT or customers, not this role's work (e.g. "the TypeScript framework we sell", "used by Shopify brands")
- Ignore company/vendor names given as examples (xAI, Anthropic, OpenAI)
- Always small letters, one name per skill:
  - "postgres" → `postgresql`, "js" → `javascript`, "k8s" → `kubernetes`
  - "Apache Airflow" → `airflow`, "Microsoft Azure" → `azure`, "Google Cloud"/"GCP" → `gcp`
  - "Ruby on Rails" → `rails`, "Tailwind CSS" → `tailwind`, "Hugging Face" → `huggingface`, "LLMs" → `llm`
  - "TanStack Query/Router" → `tanstack`

## Added on Day 5 (postings 31–50, labeled with AI help)
- Office tools (Word, Google Sheets, Slack, CRM software) are not technical skills.
- A commission-only "expected earnings" range counts as salary.
- "$XXX" or other placeholders → no salary stated.
- A backwards range ("$180k – 160k") → smallest number in salary_min.
- "Associate" in a title → `junior`.
- "Vertex AI" / "GCP Vertex AI" → `vertex ai`.