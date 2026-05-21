from .state import TaskAState

from anthropic import AsyncAnthropic
from groq import AsyncGroq 

from ...schemas.user_profile import UserProfile, TaskAResponse 
from .state import TaskAState

from ...prompts.loader import render_prompt
from ...config import get_settings

import json

settings = get_settings()


class AgentA:
    def __init__(self): 
        self.anthropic = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.groq = AsyncGroq(api_key=settings.GROQ_API_KEY)

    def analyze_user(self, state: TaskAState) -> TaskAState: 
        profile: UserProfile = state["profile"]

        state["user_analysis"] = {
            "user_id": profile.user_id, 
            "name": profile.name or "Unknown", 
            "tier": profile.tier, 
            "confidence_score": profile.confidence_score,
            "total_reviews": profile.total_reviews, 
            "average_stars": profile.rating_behaviour.average_stars, 
            "tend_to_inflate": profile.rating_behaviour.tends_to_inflate,
            "tend_to_deflate": profile.rating_behaviour.tends_to_deflate, 
            "distribution": profile.rating_behaviour.distribution,
            "top_categories": profile.category_preference.top_categories, 
            "avoided_categories": profile.category_preference.avoided_categories, 
            "tone": profile.writing_style.tone, 
            "avg_review_length": profile.writing_style.avg_review_length, 
            "common_phrases": profile.writing_style.common_phrases, 
            "uses_pidgin": profile.writing_style.uses_pidgin,
            "uses_emoji": profile.writing_style.uses_emoji,
            "formality_score": profile.writing_style.formality_score,

            "review_history": [
                {
                    "item_name": r.item_name, 
                    "stars_given": r.stars_given, 
                    "category": r.catgory, 
                    "review_snippet": r.review_snippet, 
                    "date": r.date
                } for r in profile.review_history[:10]
            ],

            "nigerian_context": {
                "is_nigerian_context": profile.nigerian_context.is_nigerian_context, 
                "local_references": profile.nigerian_context.local_references, 
                "pidgin_vocabulary": profile.nigerian_context.pidgin_vocabulary, 
                "price_sensitivity": profile.nigerian_context.price_sensitivity
            }

        }

        return state 
    


    def analyze_item(self, state: TaskAState) -> TaskAState:
        profile = state["profile"]
        item = state["item"]
        user = state["user_analysis"]

        top_cats = [c.lower() for c in user["top_categories"]]
        avoided_cats = [c.lower() for c in user["avoided_categories"]]
        item_cats = [item.category.lower()] + [s.lower() for s in item.subcategories]

        category_match = any(c in top_cats for c in item_cats)
        category_avoided = any(c in avoided_cats for c in item_cats)

        community_gap = None
        if item.avg_community_rating:
            community_gap = round(item.avg_community_rating - user["average_stars"], 2)

        state["item_analysis"] = {
            "item_id": item.item_id,
            "item_name": item.name,
            "item_category": item.category,
            "item_subcategories": item.subcategories,
            "item_description": item.description or "not provided",
            "item_price_range": item.price_range or "unknown",
            "item_avg_rating": item.avg_community_rating or "unknown",
            "item_attributes": item.attributes,
            "category_match": category_match,
            "category_avoided": category_avoided,
            "community_rating_gap": community_gap,
        }

        return state



    async def predict_rating(self, state: TaskAState) -> TaskAState:
        user = state["user_analysis"]
        item = state["item_analysis"]

        prompt = render_prompt("task_a_rating.md", {**user, **item})

        # client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        # response = await self.groq.chat.completions.create(
        #     model=settings.RATING_MODEL,
        #     messages=[{"role": "user", "content": prompt}],
        #     temperature=0.1,
        #     max_tokens=300,
        # )

        response = await self.groq.chat.completions.create(
            model=settings.RATING_MODEL, 
            messages=[{"role": "user", "content": prompt}], 
            temperature=0.1, 
            max_tokens=300
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
            stars = max(1.0, min(5.0, float(data["predicted_stars"])))
            reasoning = data.get("reasoning", "")
        except (json.JSONDecodeError, KeyError, ValueError):
            state["error"] = f"Rating prediction parse failed: {raw}"
            return state

        state["predicted_stars"] = stars
        state["rating_reasoning"] = reasoning
        return state


    async def generate_review(self, state: TaskAState) -> TaskAState:
        if state.get("error"):
            return state

        user = state["user_analysis"]
        item = state["item_analysis"]
        nigerian_mode = state["nigerian_mode"]

        prompt = render_prompt("task_a_review.md", {
            **user,
            **item,
            "predicted_stars": state["predicted_stars"],
            "predicted_stars_rounded": round(state["predicted_stars"]),
            "nigerian_mode": nigerian_mode,
            "pidgin_vocabulary": user["nigerian_context"]["pidgin_vocabulary"],
            "local_references": user["nigerian_context"]["local_references"],
            "price_sensitivity": user["nigerian_context"]["price_sensitivity"],
        })

        # response = await self.anthropic.messages.create(
        #     model=settings.TASK_A_MODEL,
        #     max_tokens=600,
        #     temperature=0.8,
        #     messages=[{"role": "user", "content": prompt}]
        # )

        response = await self.groq.chat.completions.create(
            model=settings.TASK_A_MODEL, 
            max_tokens=600, 
            temperature=0.8, 
            messages=[{"role": "user", "content": prompt}]
        )

        state["generated_review"] = response.choices[0].message.content.strip()
        return state
    

    async def apply_nigerian_context(self, state: TaskAState) -> TaskAState:
        if state.get("error"):
            return state

        user = state["user_analysis"]
        review = state["generated_review"]

        refinement_prompt = f"""You wrote this review as a Nigerian consumer:

            \"\"\"{review}\"\"\"

            Check if the review already sounds authentically Nigerian.
            If it does — return it exactly as is.
            If it doesn't — lightly refine it:
            - Add 1-2 natural Pidgin phrases where they fit: {user['nigerian_context']['pidgin_vocabulary']}
            - Reference local context where it arises naturally: {user['nigerian_context']['local_references']}
            - Reflect price sensitivity: {user['nigerian_context']['price_sensitivity']}

            Do not change the rating sentiment or review length significantly.
            Output ONLY the review text.
        """

        # response = await client.messages.create(
        #     model=settings.TASK_A_MODEL,
        #     max_tokens=600,
        #     temperature=0.5,
        #     messages=[{"role": "user", "content": refinement_prompt}]
        # )

        response = await self.groq.chat.completions.create(
            messages=[{"role": "user", "content": refinement_prompt}], 
            max_tokens=600, 
            temperature=0.5, 
            model=settings.TASK_A_MODEL
        )

        state["generated_review"] = response.choices[0].message.content.strip()
        return state
    

    def build_response(self, state: TaskAState) -> TaskAState:
        if state.get("error"):
            return state

        state["result"] = TaskAResponse(
            predicted_stars=state["predicted_stars"],
            predicted_stars_rounded=round(state["predicted_stars"]),
            generated_review=state["generated_review"],
            confidence=state["profile"].confidence_score,
            reasoning=state["rating_reasoning"]
        )

        return state