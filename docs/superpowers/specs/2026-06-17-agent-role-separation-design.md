# Agent Role Separation Design

**Date:** 2026-06-17
**Status:** Approved direction for implementation planning
**Decision:** Fully separate recommendation from policy consultation/application assistance.

## Problem

The current UI has two entry points that appear to do similar work:

- Hero "나의 상황 입력" calls `POST /recommend` and shows Top 5 recommendation cards.
- "대화형 신청 도우미" calls `POST /agent/converse`; its `recommend` intent can also call `ai.recommender.recommend_policy()` and render recommendation cards inside chat.

This makes the product harder to understand. Users can see two recommendation surfaces, and a phrase such as "정책 2" can feel ambiguous. ADR-002 already intended a split where the Hero is for exploration and the chat is for consultation/execution, but the current code still lets chat initiate a fresh recommendation.

## Goal

Make the two agents have non-overlapping responsibilities:

- **Recommendation Agent:** only the Hero "나의 상황 입력" flow recommends policies.
- **Policy Assistant Agent:** the chat only explains or acts on already recommended or selected policies.

The user experience should make this obvious without reading documentation.

## Recommended Architecture

Keep the current two-surface product, but enforce a hard boundary.

### Recommendation Agent

Owned by:

- `frontend/src/App.jsx`
- `backend/main.py` `POST /recommend`
- `ai/recommender.py`
- `ai/condition_extractor.py`
- `ai/retriever.py`
- `ai/generator.py`

Responsibilities:

- Accept user profile and free-text situation.
- Extract recommendation conditions.
- Search and rank policies.
- Return Top 5 recommendation cards.
- Seed the shared conversation session with `session_id` and `cards`.

Non-responsibilities:

- Multi-turn policy Q&A.
- Application document explanation beyond initial checklist summaries.

### Policy Assistant Agent

Owned by:

- `frontend/src/components/ChatFlowPanel.jsx`
- `frontend/src/converseClient.js`
- `backend/main.py` `POST /agent/converse`
- `ai/converse_agent.py`
- `ai/intent_router.py`
- `ai/policy_chat_agent.py`
- `ai/apply_agent.py`
- `ai/benefit_estimator.py`

Responsibilities:

- Let users select a policy from the Hero recommendation session.
- Answer selected-policy questions about required documents, benefit amount, eligibility, application method, contact, deadline, and preparation.
- Start an application plan through `/agent/apply-plan`.
- If no recommendation list or selected policy exists, guide the user back to "나의 상황 입력" instead of recommending inside chat.

Non-responsibilities:

- Calling `recommend_policy()`.
- Creating a second recommendation list.
- Treating general situation descriptions as a chat recommendation request.

## Required Behavior Changes

1. Remove the direct recommendation path from `ConverseAgent`.
   - `ai/converse_agent.py` should not import or call `recommend_policy()`.
   - `ConverseAgent.respond()` should not return new recommendation cards from a fresh recommendation call.

2. Reclassify chat recommendation attempts as guidance.
   - If a chat message says "추천해줘", "정책 찾아줘", or contains recommendation condition signals, the assistant should respond with a guidance intent such as `need_recommendation` or `unclear`.
   - If `last_recommendations` exists, ask the user to choose one of those policies.
   - If `last_recommendations` is empty, tell the user to use "나의 상황 입력" first.

3. Preserve shared session selection.
   - `/recommend` should keep returning `session_id` and `cards`.
   - `ChatFlowPanel` should keep using those cards for policy selection.
   - "정책 1 신청할래" after a Hero recommendation should still select the first Hero card and return documents/application guidance.

4. Update chat copy.
   - Greeting should not ask for the user's situation.
   - Placeholder should focus on selected policy questions, e.g. `"정책 2 서류 알려줘"` or `"선택한 정책 신청 방법 알려줘"`.
   - Header should communicate "고른 정책 상담·신청 준비", not "새 정책 추천".

5. Update tests.
   - Replace tests that expect `/agent/converse` first turn to recommend policies.
   - Add tests that prove chat recommendation attempts do not call or return fresh recommendation cards.
   - Keep tests for `/recommend` seeding chat session and chat resolving "정책 N".

6. Update docs.
   - README and ADR-002 should describe the final hard separation.
   - ADR-001 should no longer present `ConverseAgent` as dispatching to recommender for recommendation.

## Acceptance Criteria

- A user can only create policy recommendations through the Hero "나의 상황 입력" form.
- The chat cannot generate a fresh Top 5 recommendation list.
- The chat can still use Hero-seeded `session_id/cards` to select "정책 N".
- The chat can still answer docs, benefit, eligibility, and apply-how questions for a selected policy.
- Existing `/recommend` API response shape remains backward compatible.
- Tests cover the new boundary.
- UI text makes the split understandable to a first-time user.

## Proposed Verification Commands

Run after implementation:

```powershell
python -m pytest tests/test_intent_router.py tests/test_converse_agent.py tests/test_converse_api_smoke.py tests/test_backend_routes.py -q
cd frontend
npm test
npm run build
```

## Notes For Claude Code Review

Claude Code should verify the design before implementation and then verify the implementation after changes. The key question is not whether chat can be more powerful. The key question is whether the product is clearer when recommendation and selected-policy assistance are strictly separated.
