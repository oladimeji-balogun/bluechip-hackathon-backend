import json 

from groq import AsyncGroq
from anthropic import AsyncAnthropic

from .state import TaskBState
from ...schemas.user_profile import TaskBResponse, RecommendationItem

from ...config import settings

from ...prompts.loader import render_prompt 


class AgentB: 

    def __init__(self): 
        self.groq = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.anthropic = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def analyze_user(self, state: TaskBState) -> TaskBState:
        profile = state["profile"]

        prompt = render_prompt("task_b_analyze.md", {
            "user_id": profile.user_id,
            "tier": profile.tier,
            "total_reviews": profile.total_reviews,
            "confidence_score": profile.confidence_score,
            "average_stars": profile.rating_behaviour.average_stars,
            "rating_std": profile.rating_behaviour.rating_std,
            "tends_to_inflate": profile.rating_behaviour.tends_to_inflate,
            "tends_to_deflate": profile.rating_behaviour.tends_to_deflate,
            "top_categories": profile.category_preference.top_categories,
            "avoided_categories": profile.category_preference.avoided_categories,
            "cross_domain_signals": profile.category_preference.cross_domain_signals,
            "review_history": [
                {
                    "item_name": r.item_name,
                    "category": r.category,
                    "stars_given": r.stars_given,
                    "review_snippet": r.review_snippet,
                }
                for r in profile.review_history[:10]
            ],
            "domain": state.get("domain") or "not specified",
            "context": state.get("context") or "not specified",
            "nigerian_mode": state["nigerian_mode"],
            "conversation_turns": len(state["conversation_history"]),
        })

        response = await self.groq.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            state["error"] = f"User analysis parse failed: {e} — raw: {raw}"
            return state

        state["user_analysis"] = data
        state["strategy"] = data.get("recommended_strategy", "preference_retrieval")
        return state
    

    async def popularity_fallback(self, state: TaskBState) -> TaskBState:
        if state.get("error"):
            return state

        profile = state["profile"]
        top_k = state["top_k"]

        # Use whatever category signals exist even for cold users
        top_cats = profile.category_preference.top_categories
        category_hint = top_cats[0] if top_cats else "Restaurants"

        prompt = render_prompt("task_b_popularity_fallback.md", {
            "tier": profile.tier,
            "category_hint": category_hint,
            "domain": state.get("domain") or "not specified",
            "context": state.get("context") or "not specified",
            "nigerian_mode": state["nigerian_mode"],
            "candidate_count": top_k * 2,
        })

        response = await self.groq.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
            state["candidates"] = data.get("candidates", [])
        except (json.JSONDecodeError, ValueError) as e:
            state["error"] = f"Popularity fallback parse failed: {e}"
            return state

        state["cold_start_used"] = True
        return state
    

    async def cross_domain_retrieval(self, state: TaskBState) -> TaskBState:
        if state.get("error"):
            return state

        profile = state["profile"]
        user_analysis = state["user_analysis"]
        top_k = state["top_k"]

        prompt = render_prompt("task_b_cross_domain.md", {
            "user_values": user_analysis.get("user_values", ""),
            "user_dislikes": user_analysis.get("user_dislikes", ""),
            "transferable_signals": user_analysis.get("transferable_signals", ""),
            "price_sensitivity": user_analysis.get("price_sensitivity", "medium"),
            "context_signals": user_analysis.get("context_signals", ""),
            "domain": state.get("domain") or "not specified",
            "context": state.get("context") or "not specified",
            "nigerian_mode": state["nigerian_mode"],
            "candidate_count": top_k * 2,
        })

        response = await self.groq.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
            state["candidates"] = data.get("candidates", [])
        except (json.JSONDecodeError, ValueError) as e:
            state["error"] = f"Cross domain retrieval parse failed: {e}"
            return state

        state["cross_domain_used"] = True
        return state
    

    async def preference_retrieval(self, state: TaskBState) -> TaskBState:
        if state.get("error"):
            return state

        profile = state["profile"]
        user_analysis = state["user_analysis"]
        top_k = state["top_k"]

        prompt = render_prompt("task_b_preference_retrieval.md", {
            "user_values": user_analysis.get("user_values", ""),
            "user_dislikes": user_analysis.get("user_dislikes", ""),
            "top_categories": profile.category_preference.top_categories[:5],
            "avoided_categories": profile.category_preference.avoided_categories,
            "average_stars": profile.rating_behaviour.average_stars,
            "price_sensitivity": user_analysis.get("price_sensitivity", "medium"),
            "context_signals": user_analysis.get("context_signals", ""),
            "highly_rated_history": [
                f"{r.item_name} ({r.category}) — {r.stars_given}★"
                for r in profile.review_history[:5]
                if r.stars_given >= 4.0
            ],
            "domain": state.get("domain") or "not specified",
            "context": state.get("context") or "not specified",
            "nigerian_mode": state["nigerian_mode"],
            "candidate_count": top_k * 2,
        })

        response = await self.groq.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
            state["candidates"] = data.get("candidates", [])
        except (json.JSONDecodeError, ValueError) as e:
            state["error"] = f"Preference retrieval parse failed: {e}"
            return state

        return state
    

    async def rank_candidates(self, state: TaskBState) -> TaskBState:
        if state.get("error"):
            return state

        profile = state["profile"]
        user_analysis = state["user_analysis"]
        candidates = state.get("candidates", [])

        if not candidates:
            state["error"] = "No candidates retrieved to rank"
            return state

        prompt = render_prompt("task_b_ranking.md", {
            "user_id": profile.user_id,
            "tier": profile.tier,
            "user_values": user_analysis.get("user_values", ""),
            "user_dislikes": user_analysis.get("user_dislikes", ""),
            "price_sensitivity": user_analysis.get("price_sensitivity", "medium"),
            "context_signals": user_analysis.get("context_signals", ""),
            "strategy_used": state["strategy"],
            "top_categories": profile.category_preference.top_categories[:5],
            "avoided_categories": profile.category_preference.avoided_categories,
            "average_stars": profile.rating_behaviour.average_stars,
            "tends_to_inflate": profile.rating_behaviour.tends_to_inflate,
            "tends_to_deflate": profile.rating_behaviour.tends_to_deflate,
            "nigerian_mode": state["nigerian_mode"],
            "nigerian_context_notes": user_analysis.get("nigerian_context_notes", ""),
            "conversation_history": state["conversation_history"],
            "candidates": candidates,
        })

        response = await self.groq.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
            state["ranked_output"] = data
        except (json.JSONDecodeError, ValueError) as e:
            state["error"] = f"Ranking parse failed: {e} — raw: {raw[:300]}"
            return state

        return state
    

    async def apply_context(self, state: TaskBState) -> TaskBState:
        if state.get("error"):
            return state

        conversation_history = state["conversation_history"]

        # Single turn — nothing to apply, pass through
        if not conversation_history:
            return state

        ranked = state.get("ranked_output", {})
        rankings = ranked.get("rankings", [])

        if not rankings:
            return state

        history_text = "\n".join([
            f"{t['role'].upper()}: {t['content']}"
            for t in conversation_history[-4:]
        ])

        prompt = render_prompt("task_b_apply_context.md", {
            "conversation_history": conversation_history[-4:],
            "current_rankings": json.dumps(rankings, indent=2),
        })

        response = await self.groq.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1000,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
            state["ranked_output"] = data
        except (json.JSONDecodeError, ValueError):
            # If re-ranking fails, keep original rankings — don't crash
            pass

        return state
    

    def build_response(self, state: TaskBState) -> TaskBState:
        if state.get("error"):
            return state

        candidates = state.get("candidates", [])
        ranked_output = state.get("ranked_output", {})
        rankings = ranked_output.get("rankings", [])
        top_k = state["top_k"]

        recommendations = []
        for r in rankings[:top_k]:
            idx = r.get("item_index", 0)
            if idx < len(candidates):
                c = candidates[idx]
                recommendations.append(RecommendationItem(
                    rank=r["rank"],
                    item_id=c["item_id"],
                    item_name=c["name"],
                    category=c["category"],
                    predicted_rating=r.get("predicted_rating", 4.0),
                    relevance_score=r.get("relevance_score", 0.5),
                    explanation=r.get("explanation", ""),
                    nigerian_relevance_note=r.get("nigerian_relevance_note")
                ))

        state["result"] = TaskBResponse(
            recommendations=recommendations,
            reasoning=ranked_output.get("overall_reasoning", ""),
            cold_start_used=state.get("cold_start_used", False),
            cross_domain_used=state.get("cross_domain_used", False)
        )

        return state