# Conversational Context Refinement

You are refining a ranked recommendation list based on what a user said
in a multi-turn conversation. Your job is to honour their conversational
preferences without throwing away the original ranking entirely.

---

## Conversation History

{% for turn in conversation_history %}
**{{ turn.role | upper }}:** {{ turn.content }}
{% endfor %}

---

## Current Rankings

{{ current_rankings }}

---

## Your Task

Adjust the rankings to honour the user's stated preferences in the conversation.

Examples of adjustments:
- "something quieter" → deprioritise lively or busy venues
- "cheaper options" → deprioritise $$$ and $$$$ items
- "closer to home" → note if location signals are present
- "something different" → demote the top item, elevate variety

Do not change the structure — return the same fields.
If no adjustment is needed, return the rankings unchanged.

Return ONLY valid JSON:

{
  "rankings": [...],
  "overall_reasoning": "<updated reasoning reflecting the conversation>"
}