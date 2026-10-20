# Idea analysis — Nebius x NVIDIA Global AI Hackathon

Scored against the four **equally weighted** official criteria (1–5), plus the two things
that decide outcomes with 25,000+ participants and 10 days left: how crowded the idea is,
and whether one person can ship it to a polished demo by **30 Oct, 10:30 pm IST**.

Stage One is pass/fail: the project must be a genuine attempt at its track and make a runtime
call to Token Factory (or run on Nebius AI Cloud) with an NVIDIA open model.

| # | Idea | Track | Tech | Design | Impact | Idea quality | Crowding | 10-day solo feasibility | Total /20 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | PR Medic (fix failing CI) | Coding | 5 | 3 | 4 | 2 | Very high | Medium | 14 |
| 2 | Legacy-to-Modern Migrator | Coding | 4 | 3 | 3 | 3 | Medium | Low | 13 |
| 3 | Research-to-Deck | Apps | 3 | 4 | 2 | 1 | Extreme | High | 10 |
| 4 | Invoice & Expense Autopilot (GST) | Apps | 4 | 4 | 4 | 3 | Medium | Medium-high | 15 |
| 5 | Second Brain | Personal | 3 | 3 | 2 | 1 | Very high | Medium | 9 |
| 6 | Private Health & Habit Coach | Personal | 3 | 3 | 2 | 2 | High | Medium | 10 |
| 7 | Warehouse Pick-and-Sort (sim) | Physical | 4 | 3 | 3 | 3 | Low | Low | 13 |
| 8 | Smart Factory Inspector | Physical | 3 | 3 | 4 | 3 | Medium | Medium | 13 |
| ★ | **ExposureLens** (config-aware CVE exposure) | Apps | 5 | 4 | 5 | 5 | Low | High (MVP built) | **19** |

## Notes per idea

1. **PR Medic** — Strong technical story and a natural fit for "agents that write, run and test code". But coding-repair agents are the most common entry type in AI hackathons and judges have seen SWE-agent style demos many times. Winning needs a sharp twist (e.g. only flaky-test triage, or infra-as-code CI failures). Real risk: sandboxed test execution eats days.
2. **Legacy Migrator** — Impressive if it works, but correctness on real codebases is hard to show honestly in 3 minutes; a half-migrated demo scores poorly on Design.
3. **Research-to-Deck** — Fits the Tavily bonus perfectly, which is exactly why hundreds of teams will build it (public repos already exist for this hackathon). Hard to stand out on "Quality of the Idea".
4. **Invoice & Expense Autopilot** — Best of the list. Concrete audience (Indian SMBs, GST), clear before/after. Check early that **Nemotron Parse** is callable on Token Factory; if not, use Nemotron Nano Omni / VL for document reading. Strongest if you can show a real small business using it.
5. **Second Brain** — Mainstream assistants already ship memory; judges will ask "why not ChatGPT/Claude?". Needs a sharp, private, niche angle to pass the novelty bar.
6. **Health Coach** — Privacy angle suits the Personal AI track, but health advice invites scrutiny and meal-photo logging needs a vision model plus careful claims. Impact case is soft.
7. **Warehouse sim** — Least crowded track, but Cosmos / GR00T / simulation pipelines plus Serverless Jobs in 10 days solo is very ambitious.
8. **Factory Inspector** — Credible impact, but without hardware or a real defect dataset the demo looks like a generic image classifier.

## Why ExposureLens wins on the criteria

- **Quality of the Idea:** "Is the vulnerable feature actually configured?" is a non-obvious, specific use of reasoning models that only someone who has done incident triage would pick. Judges explicitly reward "genuine understanding of the problem space" — 10 years of Cisco/Palo Alto work is that.
- **Technological Implementation:** uses all three Nemotron tiers exactly as the track description suggests (Ultra for serious reasoning, Nano/Super for fast calls), with a visible cost/latency ledger, deterministic evidence grounding, parallel agents, and a batch job for Serverless Jobs.
- **Potential Impact:** every emergency advisory (IOS-XE Web UI, PAN-OS GlobalProtect) costs network teams hours of manual config review; the demo shows the version scanner's false positive being ruled out with a cited line.
- **Design:** a finished product loop — upload, live agent progress, prioritised findings, mitigation with verify/rollback, downloadable report.
- **Bonus:** a functional runtime Tavily call makes it eligible for **Best Use of Tavily ($3,000)** on top of an Overall or Track award.

## Recommendation

Submit **ExposureLens** to *Best Apps and Agents*. Multiple entries are allowed if substantially
different; only start a second entry (Invoice Autopilot) if ExposureLens is fully done by 26 Oct.
One polished project beats two half-finished ones.
