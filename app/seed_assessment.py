"""
SEED ASSESSMENT — load the MVP Profile question bank into the database.

This is the "Athletic Mindset MVP Profile" situational-judgment battery: 9
constructs (Self-Efficacy, Growth Mindset, Mastery Goal Orientation, Grit,
Mental Toughness, Coachability, Team Cohesion, Emotion Regulation, Process
Orientation), 5 scenarios each, 4 response options per scenario. Every
question is response_mode="rate_all" — the athlete rates every option's
effectiveness 1-5 rather than picking one (this resists faking, see the
source document's rationale). Each option's `score` is the expert "Key"
rating from the document; these are explicitly draft/rational keys pending
the client's SME panel review, so admins can freely revise them later
through the CMS with no code changes.

Run once (and re-run safely) to populate the bank if it's empty:
    uv run python -m app.seed_assessment

Force a full replace of existing content with what's defined below (used for
this content migration, not meant to run on every startup):
    uv run python -m app.seed_assessment --reset

Sport category (team/individual/combat) and adaptive wording aren't used —
the source document specifies these scenarios are sport-agnostic by design.
"""

import asyncio
import sys

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assessment_content_sync import sync_question_content
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import (
    AssessmentDimension,
    AssessmentFactor,
    AssessmentPhase,
    AssessmentQuestion,
    AssessmentQuestionOption,
    AssessmentResponse,
    AssessmentSession,
    ContentEntry,
    MeasurementTypeEnum,
    QuestionTierEnum,
    QuestionTypeEnum,
    ResponseModeEnum,
)

# --- Taxonomy ---
# One phase, one factor per construct, one dimension per factor — this
# instrument doesn't sub-divide constructs further (unlike the prior 40-item
# bank), so dimension mirrors factor 1:1 just to satisfy the existing
# phase->factor->dimension->question shape without adding a schema change.

PHASES = [
    {"key": "mental_performance", "name": "Mental Performance Profile", "order": 0},
]

FACTORS = [
    {"key": "self_efficacy", "name": "Self-Efficacy (Competitive Confidence)", "phase_key": "mental_performance", "order": 0},
    {"key": "growth_mindset", "name": "Growth Mindset", "phase_key": "mental_performance", "order": 1},
    {"key": "mastery_goal_orientation", "name": "Mastery Goal Orientation", "phase_key": "mental_performance", "order": 2},
    {"key": "grit", "name": "Grit (Perseverance & Consistency of Interest)", "phase_key": "mental_performance", "order": 3},
    {"key": "mental_toughness", "name": "Mental Toughness / Composure Under Pressure", "phase_key": "mental_performance", "order": 4},
    {"key": "coachability", "name": "Coachability / Feedback Receptivity", "phase_key": "mental_performance", "order": 5},
    {"key": "team_cohesion", "name": "Team Cohesion & Psychological Collectivism", "phase_key": "mental_performance", "order": 6},
    {"key": "emotion_regulation", "name": "Emotion Regulation", "phase_key": "mental_performance", "order": 7},
    {"key": "process_orientation", "name": "Process Orientation", "phase_key": "mental_performance", "order": 8},
]

DIMENSIONS = [{"key": f["key"], "name": f["name"], "factor_key": f["key"], "order": 0} for f in FACTORS]


def opt(label: str, text: str, key: int) -> dict:
    return {"label": label, "text": text, "score": key, "tag": None, "order": ord(label) - ord("A")}


# --- Questions ---
# order runs 1..45 across the whole bank (5 items per construct, in the
# document's construct order). `score` on each option is the document's "Key"
# value — the expert-rated effectiveness (1=Very Ineffective..5=Very
# Effective) this option's rating is compared against.

QUESTIONS = [
    # 1. Self-Efficacy
    dict(
        order=1, dimension_key="self_efficacy", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You're facing one of the biggest moments of your season so far, against an opponent or standard you've never beaten before. Rate each response:",
        helper_text=None,
        options=[
            opt("A", "Tell yourself, “I've done this exact skill successfully many times in practice; I just need to execute what I know.”", 5),
            opt("B", "Tell yourself, “I hope I don't choke like last time.”", 1),
            opt("C", "Avoid thinking about it at all and hope your body “just knows what to do.”", 2),
            opt("D", "Remind yourself of a specific past performance where you executed this exact skill well.", 5),
        ],
    ),
    dict(
        order=2, dimension_key="self_efficacy", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You haven't succeeded on your last several attempts in a competition. Your coach gives you another chance on the next big opportunity.",
        helper_text=None,
        options=[
            opt("A", "Think, “I'm cooked today, someone else should take this.”", 1),
            opt("B", "Focus on the process cues that have worked before (“balance, follow-through”) rather than the miss count.", 5),
            opt("C", "Get angry at yourself internally to “motivate” harder effort.", 2),
            opt("D", "Ask a teammate for a quick reset cue or word of encouragement.", 4),
        ],
    ),
    dict(
        order=3, dimension_key="self_efficacy", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A new training block introduces a skill/technique you've never attempted (e.g., a new team strategy, a harder skill progression).",
        helper_text=None,
        options=[
            opt("A", "Assume you'll be bad at it since you've never done it and hold back effort to avoid embarrassment.", 1),
            opt("B", "Break it into smaller components you can master progressively before attempting it fully.", 5),
            opt("C", "Watch a teammate who's good at it and mentally rehearse the movement before trying.", 4),
            opt("D", "Attempt it full-speed immediately with no lead-up, regardless of readiness.", 2),
        ],
    ),
    dict(
        order=4, dimension_key="self_efficacy", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You're warming up before a competition and notice the opponent looks bigger/faster/more decorated than you.",
        helper_text=None,
        options=[
            opt("A", "Focus on your own preparation and what you specifically control (your routine, your competition plan).", 5),
            opt("B", "Compare your stats to theirs to decide if you belong at this level.", 2),
            opt("C", "Seek out a coach or teammate to talk through your competition plan one more time.", 4),
            opt("D", "Let the comparison sit in your head and hope it doesn't affect you.", 1),
        ],
    ),
    dict(
        order=5, dimension_key="self_efficacy", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="After a poor individual performance in a team loss, a coach or teammate asks how you're feeling about your form heading into next week.",
        helper_text=None,
        options=[
            opt("A", "Explain specifically what went wrong and what you're already fixing in practice this week.", 5),
            opt("B", "Express doubt about whether you still have the ability to perform well.", 1),
            opt("C", "Attribute the poor performance entirely to external conditions, not your own execution.", 2),
            opt("D", "Give a vague answer about grinding it out without a specific plan.", 3),
        ],
    ),
    # 2. Growth Mindset
    dict(
        order=6, dimension_key="growth_mindset", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You get cut from an elite squad/team or lose your regular playing/competing role.",
        helper_text=None,
        options=[
            opt("A", "Conclude you've hit your ceiling and this sport isn't for you.", 1),
            opt("B", "Ask the coach specifically what to work on to be considered again.", 5),
            opt("C", "Blame the coach's favoritism and disengage from extra training.", 1),
            opt("D", "Increase training volume without seeking specific feedback on what to change.", 3),
        ],
    ),
    dict(
        order=7, dimension_key="growth_mindset", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A teammate who used to be worse than you has now surpassed your skill level.",
        helper_text=None,
        options=[
            opt("A", "Assume they're just “naturally gifted” and there's nothing to learn from it.", 1),
            opt("B", "Ask them what specifically changed in their training or mindset.", 5),
            opt("C", "Feel threatened and start avoiding training with them.", 2),
            opt("D", "Quietly increase your own effort without addressing what's different in your approach.", 3),
        ],
    ),
    dict(
        order=8, dimension_key="growth_mindset", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You receive harsh but specific technical feedback from a coach in front of the team.",
        helper_text=None,
        options=[
            opt("A", "Shut down and assume the coach thinks you're not good enough, period.", 1),
            opt("B", "Separate the feedback on the skill from your sense of self-worth and note the specific correction.", 5),
            opt("C", "Get defensive and explain why the mistake wasn't really your fault.", 2),
            opt("D", "Nod along but privately dismiss the feedback as the coach “not getting it.”", 1),
        ],
    ),
    dict(
        order=9, dimension_key="growth_mindset", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You've plateaued on a specific performance metric you track (e.g., a time, a max effort, an accuracy rate) for several months.",
        helper_text=None,
        options=[
            opt("A", "Conclude that's just your genetic ceiling for that metric.", 1),
            opt("B", "Experiment with a new training method or seek a specialist's input.", 5),
            opt("C", "Keep doing the exact same program, assuming consistency alone will break the plateau.", 2),
            opt("D", "Reduce effort on that metric and focus only on things you're already good at.", 2),
        ],
    ),
    dict(
        order=10, dimension_key="growth_mindset", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A teammate says, “I'm just not a natural at this like my sibling.”",
        helper_text=None,
        options=[
            opt("A", "Agree, and suggest they try a different sport instead.", 1),
            opt("B", "Explain that skill in this sport is built through specific, repeatable practice, and offer a concrete next step.", 5),
            opt("C", "Tell them “everyone's a natural at something, just keep trying” with no specific plan.", 3),
            opt("D", "Tell them talent doesn't matter at all and only hard work exists.", 2),
        ],
    ),
    # 3. Mastery Goal Orientation
    dict(
        order=11, dimension_key="mastery_goal_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You finish 2nd, with your best individual performance of the season, while the athlete who finished 1st performed below their own season best.",
        helper_text=None,
        options=[
            opt("A", "Feel like a failure because you didn't win.", 2),
            opt("B", "Recognize your own season-best performance as the core measure of success, and still note what to sharpen for next time.", 5),
            opt("C", "Feel satisfied only because you beat most of the field, disregarding your own performance level.", 2),
            opt("D", "Dismiss the result because “the competition wasn't strong enough to matter.”", 1),
        ],
    ),
    dict(
        order=12, dimension_key="mastery_goal_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="Preseason goal-setting: your coach asks you to set a personal target for the year.",
        helper_text=None,
        options=[
            opt("A", "Set a goal purely based on beating a specific rival.", 2),
            opt("B", "Set a goal tied to a specific, controllable improvement in your own performance (e.g., a technical or conditioning benchmark).", 5),
            opt("C", "Set a vague goal like “be the best” with no defined benchmark.", 2),
            opt("D", "Set a goal solely about earning a featured role, spot, or award, regardless of the skill development behind it.", 3),
        ],
    ),
    dict(
        order=13, dimension_key="mastery_goal_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You win a competition but know your performance was sloppy and below your standard.",
        helper_text=None,
        options=[
            opt("A", "Feel fully satisfied — a win is a win.", 2),
            opt("B", "Feel genuinely conflicted, and review film to identify what to fix despite the win.", 5),
            opt("C", "Feel embarrassed and avoid reviewing the performance at all.", 2),
            opt("D", "Assume the win proves no changes are needed.", 1),
        ],
    ),
    dict(
        order=14, dimension_key="mastery_goal_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="Midway through a rebuilding season where the team is losing more than winning.",
        helper_text=None,
        options=[
            opt("A", "Disengage from practice since results “don't matter” this year.", 1),
            opt("B", "Set individual and team development targets to track versus prior weeks, independent of the win/loss record.", 5),
            opt("C", "Focus entirely on the scoreboard and become increasingly frustrated week to week.", 2),
            opt("D", "Blame teammates for the results and stop trying to improve your own performance.", 1),
        ],
    ),
    dict(
        order=15, dimension_key="mastery_goal_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="After a tough loss, your coach asks the team what went well individually, despite the result.",
        helper_text=None,
        options=[
            opt("A", "Say “nothing,” since the team lost.", 2),
            opt("B", "Identify one or two specific things you personally executed better than in past competitions.", 5),
            opt("C", "Deflect and only critique teammates' performances.", 1),
            opt("D", "Say generic things like “we tried hard” without specifics.", 3),
        ],
    ),
    # 4. Grit
    dict(
        order=16, dimension_key="grit", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You're many months into recovering from a significant injury, with no guarantee you'll return to your prior level.",
        helper_text=None,
        options=[
            opt("A", "Quit the sport since the outcome is uncertain.", 1),
            opt("B", "Keep a long-term target while adjusting the daily plan based on what the body allows.", 5),
            opt("C", "Push through every session regardless of medical guidance to “prove toughness.”", 2),
            opt("D", "Do the rehab inconsistently, only when motivated.", 2),
        ],
    ),
    dict(
        order=17, dimension_key="grit", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A new, flashier sport/training trend is attracting your training partners, while your event/position feels repetitive.",
        helper_text=None,
        options=[
            opt("A", "Switch focus areas frequently, chasing whatever feels novel.", 2),
            opt("B", "Stay committed to your core event/role while finding new ways to make training engaging.", 5),
            opt("C", "Keep grinding the same routine with zero variation, tolerating boredom rather than addressing it.", 3),
            opt("D", "Quit your role because it's “not exciting anymore.”", 1),
        ],
    ),
    dict(
        order=18, dimension_key="grit", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You've had three consecutive losing seasons in a program that's rebuilding.",
        helper_text=None,
        options=[
            opt("A", "Quit the team immediately at the first sign of adversity.", 2),
            opt("B", "Reassess whether the long-term goal is still worth pursuing here, and if so, recommit with a clear plan.", 5),
            opt("C", "Stay only out of obligation, with no real reinvestment of effort.", 2),
            opt("D", "Blame the program publicly and check out mentally while still nominally on the roster.", 1),
        ],
    ),
    dict(
        order=19, dimension_key="grit", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="Off-season training is unglamorous, unsupervised, and results won't show for months.",
        helper_text=None,
        options=[
            opt("A", "Skip most sessions since no one is watching.", 1),
            opt("B", "Maintain a consistent training log/plan tied to your season-long goal, even without external accountability.", 5),
            opt("C", "Train hard only right before season starts.", 2),
            opt("D", "Set your training schedule based on daily mood.", 2),
        ],
    ),
    dict(
        order=20, dimension_key="grit", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You experience a significant setback (major loss, injury, being benched) right before a goal you've pursued for years.",
        helper_text=None,
        options=[
            opt("A", "Treat the setback as proof the multi-year goal was never realistic and abandon it.", 1),
            opt("B", "Accept the setback, then adjust the timeline or approach while keeping the underlying goal.", 5),
            opt("C", "Ignore the setback entirely and pretend nothing happened.", 2),
            opt("D", "Rehash the setback repeatedly without adjusting any plan.", 2),
        ],
    ),
    # 5. Mental Toughness / Composure Under Pressure
    dict(
        order=21, dimension_key="mental_toughness", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You make a costly error late in a close competition with the outcome still in doubt.",
        helper_text=None,
        options=[
            opt("A", "Dwell on the error while the play/point continues, missing your next assignment.", 1),
            opt("B", "Use a quick reset routine (breath, cue word) and refocus on the very next action.", 5),
            opt("C", "Play more cautiously the rest of the competition to avoid another mistake.", 2),
            opt("D", "Confront yourself harshly to “lock in,” even if it disrupts your next play or point.", 2),
        ],
    ),
    dict(
        order=22, dimension_key="mental_toughness", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="The crowd/environment turns hostile (booing, heckling, unfavorable officiating) during competition.",
        helper_text=None,
        options=[
            opt("A", "Engage verbally with the crowd/officials to defend yourself.", 1),
            opt("B", "Narrow your attention to task-relevant cues and ignore crowd noise.", 5),
            opt("C", "Let frustration build silently, affecting your body language and focus.", 2),
            opt("D", "Ask a teammate/coach for a quick word to refocus in the moment.", 4),
        ],
    ),
    dict(
        order=23, dimension_key="mental_toughness", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="In sudden-death or a final decisive moment, your heart rate spikes and hands are shaking.",
        helper_text=None,
        options=[
            opt("A", "Interpret the energy as a sign you're not ready and start to panic.", 1),
            opt("B", "Use a pre-performance routine to channel the energy into focused readiness.", 5),
            opt("C", "Try to suppress all feeling and “go numb.”", 2),
            opt("D", "Rush the action to get it over with as fast as possible.", 2),
        ],
    ),
    dict(
        order=24, dimension_key="mental_toughness", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A close opponent begins trash-talking to get under your skin.",
        helper_text=None,
        options=[
            opt("A", "Respond in kind to “not back down.”", 1),
            opt("B", "Stay focused on your own competition plan and let your performance respond instead.", 5),
            opt("C", "Withdraw effort to avoid further confrontation.", 2),
            opt("D", "Report it to an official/coach and continue competing your way.", 4),
        ],
    ),
    dict(
        order=25, dimension_key="mental_toughness", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You're leading late, and the opponent mounts a comeback, shifting momentum.",
        helper_text=None,
        options=[
            opt("A", "Start playing not to lose, becoming overly conservative.", 2),
            opt("B", "Maintain the same aggressive approach and process that built the lead.", 5),
            opt("C", "Panic and abandon the game plan entirely.", 1),
            opt("D", "Get frustrated at teammates for “letting up.”", 1),
        ],
    ),
    # 6. Coachability / Feedback Receptivity
    dict(
        order=26, dimension_key="coachability", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A coach gives you a technical correction you privately disagree with.",
        helper_text=None,
        options=[
            opt("A", "Ignore the instruction and keep doing it your way in games.", 1),
            opt("B", "Try the correction in practice with genuine effort before forming a final opinion.", 5),
            opt("C", "Comply only when the coach is watching.", 2),
            opt("D", "Argue the point extensively in the moment during a live session.", 2),
        ],
    ),
    dict(
        order=27, dimension_key="coachability", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You want to know why you're not getting more playing time.",
        helper_text=None,
        options=[
            opt("A", "Assume it's political and stop putting in extra effort.", 1),
            opt("B", "Ask the coach directly and specifically what to improve to earn more time.", 5),
            opt("C", "Complain to teammates instead of addressing it directly.", 1),
            opt("D", "Wait silently, hoping the coach notices your effort eventually.", 2),
        ],
    ),
    dict(
        order=28, dimension_key="coachability", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="After review, a coach points out the same technical flaw for the third week in a row.",
        helper_text=None,
        options=[
            opt("A", "Get defensive since you feel you're already trying.", 2),
            opt("B", "Ask for a specific drill or cue to target that exact flaw.", 5),
            opt("C", "Nod but make no behavior change in the next session.", 1),
            opt("D", "Ask a teammate to relay to the coach that you're already working on it.", 2),
        ],
    ),
    dict(
        order=29, dimension_key="coachability", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A younger or less-experienced coach gives you feedback that challenges how you've always done things.",
        helper_text=None,
        options=[
            opt("A", "Dismiss it because of the coach's relative experience level.", 1),
            opt("B", "Evaluate the content of the feedback on its merits, regardless of who delivered it.", 5),
            opt("C", "Comply outwardly while privately disregarding it.", 2),
            opt("D", "Ask clarifying questions to understand the reasoning behind the feedback.", 4),
        ],
    ),
    dict(
        order=30, dimension_key="coachability", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You disagree strongly with a tactical decision (role change, event change, position switch) made by the coaching staff.",
        helper_text=None,
        options=[
            opt("A", "Publicly express frustration to teammates before addressing the coach.", 1),
            opt("B", "Request a private conversation to understand the reasoning and share your perspective.", 5),
            opt("C", "Comply silently while resenting the decision and disengaging effort.", 2),
            opt("D", "Refuse the assignment until it's changed.", 1),
        ],
    ),
    # 7. Team Cohesion & Psychological Collectivism (each item probes a named facet)
    dict(
        order=31, dimension_key="team_cohesion", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A new stat/highlight-tracking system starts publicizing individual performance metrics.",
        helper_text="Goal Priority facet",
        options=[
            opt("A", "Adjust your play style to maximize your personal stats even if it hurts team success.", 1),
            opt("B", "Keep prioritizing the team's tactical needs, using the stats as one input among many.", 5),
            opt("C", "Ignore the system completely and refuse engagement with any performance data.", 3),
            opt("D", "Pressure teammates to help you to boost your numbers.", 1),
        ],
    ),
    dict(
        order=32, dimension_key="team_cohesion", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A play/strategy calls for you to trust a teammate to cover a task or space while you focus on your own assignment.",
        helper_text="Reliance facet",
        options=[
            opt("A", "Try to cover both your assignment and theirs yourself, “just in case.”", 2),
            opt("B", "Trust your teammate to execute their part and fully commit to your own assignment.", 5),
            opt("C", "Skip your own assignment to double-check theirs, disrupting the team's plan.", 1),
            opt("D", "Do your assignment half-heartedly since you're unsure they'll do theirs.", 2),
        ],
    ),
    dict(
        order=33, dimension_key="team_cohesion", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A teammate is struggling and it's affecting overall team performance.",
        helper_text="Concern facet",
        options=[
            opt("A", "Publicly criticize them to the group.", 1),
            opt("B", "Offer specific, private support or ask what they need from the group.", 5),
            opt("C", "Avoid the topic entirely to prevent awkwardness.", 2),
            opt("D", "Complain to other teammates about the struggling player, not the player themselves.", 1),
        ],
    ),
    dict(
        order=34, dimension_key="team_cohesion", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="A role change would help the team but reduce your individual spotlight (e.g., moving from a role focused on individual recognition to one focused on supporting teammates).",
        helper_text="Preference facet",
        options=[
            opt("A", "Resist the change and lobby to keep your old role regardless of team fit.", 1),
            opt("B", "Accept the role change and ask how to excel within it.", 5),
            opt("C", "Accept outwardly, but visibly sulk or under-invest in the new role.", 1),
            opt("D", "Accept but continue trying to play the old role during competition anyway.", 1),
        ],
    ),
    dict(
        order=35, dimension_key="team_cohesion", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="Your team has a long-standing tradition or routine (a specific warm-up, a pregame ritual, a way film review is run) that you personally find pointless or would rather skip.",
        helper_text="Norm Acceptance facet",
        options=[
            opt("A", "Skip it quietly whenever you think it doesn't matter.", 1),
            opt("B", "Participate fully, since it matters to team culture even if you wouldn't have chosen it yourself.", 5),
            opt("C", "Go along with it but complain about it to teammates.", 2),
            opt("D", "Openly push to eliminate it before understanding why the team values it.", 2),
        ],
    ),
    # 8. Emotion Regulation
    dict(
        order=36, dimension_key="emotion_regulation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You notice pre-competition nerves (racing heart, shallow breathing) an hour before a major event.",
        helper_text=None,
        options=[
            opt("A", "Try to eliminate the nerves completely through distraction (phone, unrelated tasks).", 2),
            opt("B", "Use a structured routine (breathing, activation cues) to bring energy to your known optimal level.", 5),
            opt("C", "Interpret the nerves as a bad sign and spiral into worry.", 1),
            opt("D", "Ignore the sensations and hope they pass on their own.", 2),
        ],
    ),
    dict(
        order=37, dimension_key="emotion_regulation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You feel flat and low-energy before a competition that matters less to you (e.g., an early-round or “easy” opponent).",
        helper_text=None,
        options=[
            opt("A", "Assume low energy doesn't matter since the opponent is weaker.", 2),
            opt("B", "Use an activation routine (music, movement, self-talk) to raise energy to an effective level regardless of opponent.", 5),
            opt("C", "Wait passively for adrenaline to appear once competition starts.", 2),
            opt("D", "Deliberately underperform since it “doesn't matter.”", 1),
        ],
    ),
    dict(
        order=38, dimension_key="emotion_regulation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You feel a surge of anger after a bad call or an opponent's unsportsmanlike behavior.",
        helper_text=None,
        options=[
            opt("A", "Let the anger fuel a reckless or retaliatory action.", 1),
            opt("B", "Acknowledge the anger, then use a specific technique (breath, cue word) to channel it into focused intensity.", 5),
            opt("C", "Suppress the anger entirely and act as if nothing happened, ignoring the residual tension.", 2),
            opt("D", "Vent visibly to officials at length before returning focus to the game.", 1),
        ],
    ),
    dict(
        order=39, dimension_key="emotion_regulation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="Between periods/sets/innings/rounds in a close contest, your emotional state is see-sawing between anxiety and overconfidence.",
        helper_text=None,
        options=[
            opt("A", "Let emotions run their course without any intentional regulation.", 2),
            opt("B", "Use a consistent break-time routine to stabilize your state regardless of the emotional swing.", 5),
            opt("C", "Try to hype yourself up regardless of your actual internal state.", 2),
            opt("D", "Avoid teammates/coach during the break to “manage it alone” every time.", 2),
        ],
    ),
    dict(
        order=40, dimension_key="emotion_regulation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You're competing through minor pain/discomfort that isn't injury-risk but is uncomfortable and distracting.",
        helper_text=None,
        options=[
            opt("A", "Catastrophize the discomfort, letting it dominate your attention.", 1),
            opt("B", "Acknowledge the sensation without judgment and redirect focus to performance cues.", 5),
            opt("C", "Grit your teeth and mentally fight the sensation, increasing overall tension.", 2),
            opt("D", "Communicate with staff between stoppages if it's affecting performance, then refocus.", 4),
        ],
    ),
    # 9. Process Orientation
    dict(
        order=41, dimension_key="process_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You execute a technically sound attempt, but the outcome doesn't go your way due to circumstances outside your control (e.g., an opponent makes a great counter, an unlucky break, an unfavorable judgment call).",
        helper_text=None,
        options=[
            opt("A", "Judge the attempt as a failure purely because the result was negative.", 1),
            opt("B", "Evaluate the attempt based on whether the technique and decision were sound, independent of the result.", 5),
            opt("C", "Change your technique immediately based on this one outcome.", 2),
            opt("D", "Feel demoralized and carry that feeling into your next attempt.", 1),
        ],
    ),
    dict(
        order=42, dimension_key="process_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You're in the middle of a long competition (a match, a race, a multi-event day) and you're behind on the scoreboard/clock.",
        helper_text=None,
        options=[
            opt("A", "Fixate on the scoreboard and calculate what you'd need to do to catch up.", 2),
            opt("B", "Return attention to the next specific action (next point, next stride, next rep) and execute it on its own merits.", 5),
            opt("C", "Panic and abandon your game plan to chase the score.", 1),
            opt("D", "Mentally check out since the scoreboard looks out of reach.", 1),
        ],
    ),
    dict(
        order=43, dimension_key="process_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="Before a high-stakes competition, a teammate keeps talking about “we have to win this” and what winning would mean.",
        helper_text=None,
        options=[
            opt("A", "Join in and let the outcome talk dominate your own pre-competition focus.", 2),
            opt("B", "Acknowledge the stakes, then redirect your own attention to your specific process goals for the day.", 5),
            opt("C", "Get visibly annoyed and shut the teammate down harshly.", 2),
            opt("D", "Say nothing but let the outcome-talk increase your anxiety silently.", 1),
        ],
    ),
    dict(
        order=44, dimension_key="process_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="After a win, your coach asks you to reflect on the performance.",
        helper_text=None,
        options=[
            opt("A", "Say it was a good performance because you won, with no further detail.", 2),
            opt("B", "Identify specific process elements (decisions, technique, effort) that worked, separate from the result.", 5),
            opt("C", "Focus only on the parts of the performance that went badly, ignoring the process evaluation.", 2),
            opt("D", "Avoid reflecting at all since the result was positive.", 1),
        ],
    ),
    dict(
        order=45, dimension_key="process_orientation", question_type="scenario", measurement_type="trait",
        tier="free", response_mode="rate_all",
        prompt="You have one attempt/play left and it will decide the outcome of the competition.",
        helper_text=None,
        options=[
            opt("A", "Think explicitly about what winning or losing will mean for your season/reputation.", 1),
            opt("B", "Narrow focus to the specific technical cue or process step needed to execute this attempt.", 5),
            opt("C", "Rush the attempt to relieve the pressure of the moment.", 2),
            opt("D", "Try to clear your mind of everything, including your usual process cues.", 2),
        ],
    ),
]


async def _seed_taxonomy_and_questions(db: AsyncSession) -> None:
    phase_by_key: dict[str, AssessmentPhase] = {}
    for p in PHASES:
        phase = AssessmentPhase(key=p["key"], name=p["name"], order=p["order"])
        db.add(phase)
        phase_by_key[p["key"]] = phase
    await db.flush()

    factor_by_key: dict[str, AssessmentFactor] = {}
    for f in FACTORS:
        factor = AssessmentFactor(
            phase_id=phase_by_key[f["phase_key"]].id, key=f["key"], name=f["name"], order=f["order"]
        )
        db.add(factor)
        factor_by_key[f["key"]] = factor
    await db.flush()

    dimension_by_key: dict[str, AssessmentDimension] = {}
    for d in DIMENSIONS:
        dimension = AssessmentDimension(
            factor_id=factor_by_key[d["factor_key"]].id, key=d["key"], name=d["name"], order=d["order"]
        )
        db.add(dimension)
        dimension_by_key[d["key"]] = dimension
    await db.flush()

    for q in QUESTIONS:
        question = AssessmentQuestion(
            dimension_id=dimension_by_key[q["dimension_key"]].id,
            order=q["order"],
            prompt=q["prompt"],
            helper_text=q.get("helper_text"),
            question_type=QuestionTypeEnum(q["question_type"]),
            measurement_type=MeasurementTypeEnum(q["measurement_type"]),
            tier=QuestionTierEnum(q["tier"]),
            response_mode=ResponseModeEnum(q["response_mode"]),
            reverse_scored=False,
        )
        question.options = [AssessmentQuestionOption(**o) for o in q["options"]]
        db.add(question)
    await db.flush()


async def _backfill_missing_question_content(db: AsyncSession) -> None:
    """Populate ContentEntry translation rows for any question that doesn't have them yet."""
    master = settings.CONTENT_MASTER_LOCALE
    result = await db.execute(select(AssessmentQuestion).options(selectinload(AssessmentQuestion.options)))
    questions = result.scalars().all()
    if not questions:
        return

    synced_result = await db.execute(
        select(ContentEntry.key).where(
            ContentEntry.locale == master, ContentEntry.key.like("assessment.questions.%.prompt")
        )
    )
    synced_prompt_keys = {row[0] for row in synced_result.all()}

    missing = [q for q in questions if f"assessment.questions.{q.id}.prompt" not in synced_prompt_keys]
    if not missing:
        return

    for question in missing:
        await sync_question_content(db, question)
    await db.commit()
    print(f"✅ Backfilled assessment translation content for {len(missing)} question(s).")


async def ensure_seeded() -> None:
    """
    Populate the assessment tables if they're empty, then make sure every
    question's translation content is in sync. Safe to call on every startup.
    """
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(AssessmentPhase.id).limit(1))
        if existing.scalar_one_or_none() is None:
            await _seed_taxonomy_and_questions(db)
            await db.commit()
            print(f"✅ Seeded assessment bank: {len(PHASES)} phases, {len(FACTORS)} factors, "
                  f"{len(DIMENSIONS)} dimensions, {len(QUESTIONS)} questions.")

        await _backfill_missing_question_content(db)


async def reset_and_reseed() -> None:
    """
    Force-clear all existing assessment content (and any in-progress/complete
    sessions referencing it) and load the bank defined above fresh. This is a
    deliberate one-time content migration — not run automatically on startup.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AssessmentResponse))
        await db.execute(delete(AssessmentSession))
        await db.execute(delete(AssessmentPhase))  # cascades to factors/dimensions/questions/options
        await db.execute(delete(ContentEntry).where(ContentEntry.key.like("assessment.questions.%")))
        await db.commit()

        await _seed_taxonomy_and_questions(db)
        await db.commit()
        print(f"✅ Reset and reseeded: {len(PHASES)} phases, {len(FACTORS)} factors, "
              f"{len(DIMENSIONS)} dimensions, {len(QUESTIONS)} questions.")

        await _backfill_missing_question_content(db)


if __name__ == "__main__":
    if "--reset" in sys.argv:
        asyncio.run(reset_and_reseed())
    else:
        asyncio.run(ensure_seeded())
