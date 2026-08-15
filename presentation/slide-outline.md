# Slide Outline — Expense Approval Workflow: Durable Functions vs. Logic Apps

Use this as your speaker-note script when recording. ~12 slides fits a 10–15 min video
at roughly 60–75 seconds/slide.

1. **Title** — project name, your name, course
2. **The Workflow & Business Rules** — one diagram: input → validate → <$100 auto /
   ≥$100 manager approval (with timeout) → notify. State the rules table from the
   assignment in your own words.
3. **Version A Architecture** — diagram: HTTP client fn → orchestrator → activities
   (validate, notify), with the timer/event race called out visually.
4. **Version A Key Decisions** — timeout length choice, why activities are split the
   way they are, how validation errors short-circuit the chain.
5. **Version A Live Demo** — screen recording: submit low-amount (auto-approve),
   submit high-amount + call decision endpoint, show status query result.
6. **Version B Architecture** — diagram: queue → Logic App → validation Function →
   condition branches → topic w/ 3 filtered subscriptions → email.
7. **Version B Key Decisions** — the polling approach to human interaction and why
   (state the limitation honestly — this is a strong slide if handled directly).
8. **Version B Live Demo** — screenshots/recording: Service Bus Explorer send message,
   Logic App run history, subscription counts changing, email received.
9. **Comparison — Dev Experience & Testability** — side-by-side table or two columns.
10. **Comparison — Error Handling, Human Interaction, Observability** — second table.
11. **Comparison — Cost** — your Pricing Calculator numbers at 100/day and 10,000/day.
12. **Recommendation & Lessons Learned** — your verdict, when you'd pick the other
    approach, and 2–3 genuine surprises from building both.

Once you've filled in your real numbers/screenshots, tell me and I can generate the
actual .pptx file from this outline.
