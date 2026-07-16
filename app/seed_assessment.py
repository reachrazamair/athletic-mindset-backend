"""
SEED ASSESSMENT — load the initial 40-question bank into the database.

Run once (and re-run safely) to populate the assessment taxonomy, questions,
and options. Mirrors seed_content.py's idempotency pattern: this is bootstrap
data only. Once seeded, every row is a normal database record that admins
add/edit/delete/reorder from the CMS — nothing here is read by the
application again after the initial load.

Sport category (team/individual/combat) isn't seeded here — it's entered
directly by the athlete as part of the assessment's own registration step,
not an admin-curated lookup (see AM Assessment Framework v1, Section 1).

    uv run python -m app.seed_assessment
"""

import asyncio

from sqlalchemy import select
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
    ContentEntry,
    MeasurementTypeEnum,
    QuestionTierEnum,
    QuestionTypeEnum,
)

# --- Taxonomy ---

PHASES = [
    {"key": "preparation", "name": "Preparation", "order": 0},
    {"key": "competition", "name": "Competition", "order": 1},
    {"key": "teamwork", "name": "Teamwork", "order": 2},
]

FACTORS = [
    {"key": "grit", "name": "Grit", "phase_key": "preparation", "order": 0},
    {"key": "workstyle", "name": "Workstyle", "phase_key": "preparation", "order": 1},
    {"key": "coachability", "name": "Coachability", "phase_key": "preparation", "order": 2},
    {"key": "drive", "name": "Drive", "phase_key": "competition", "order": 0},
    {"key": "focus", "name": "Focus", "phase_key": "competition", "order": 1},
    {"key": "mental_toughness", "name": "Mental Toughness", "phase_key": "competition", "order": 2},
    {"key": "leadership_potential", "name": "Leadership Potential", "phase_key": "teamwork", "order": 0},
    {"key": "team_orientation", "name": "Team Orientation", "phase_key": "teamwork", "order": 1},
    {"key": "situational_mindsets", "name": "Situational Mindsets", "phase_key": "teamwork", "order": 2},
]

DIMENSIONS = [
    {"key": "persistence", "name": "Persistence", "factor_key": "grit", "order": 0},
    {"key": "intrinsic_motivation", "name": "Intrinsic Motivation", "factor_key": "grit", "order": 1},
    {"key": "extrinsic_motivation", "name": "Extrinsic Motivation", "factor_key": "grit", "order": 2},
    {"key": "engagement", "name": "Engagement", "factor_key": "grit", "order": 3},
    {"key": "work_ethic", "name": "Work Ethic", "factor_key": "workstyle", "order": 0},
    {"key": "growth_mindset", "name": "Growth Mindset", "factor_key": "workstyle", "order": 1},
    {"key": "goal_orientation_practice", "name": "Goal Orientation (Practice)", "factor_key": "workstyle", "order": 2},
    {"key": "feedback_acceptance", "name": "Feedback Acceptance", "factor_key": "coachability", "order": 0},
    {"key": "humility", "name": "Humility", "factor_key": "coachability", "order": 1},
    {"key": "adherence_to_direction", "name": "Adherence to Direction", "factor_key": "coachability", "order": 2},
    {"key": "entitlement", "name": "Entitlement", "factor_key": "coachability", "order": 3},
    {"key": "competitiveness", "name": "Competitiveness", "factor_key": "drive", "order": 0},
    {"key": "intensity", "name": "Intensity", "factor_key": "drive", "order": 1},
    {"key": "goal_orientation_performance", "name": "Goal Orientation (Performance)", "factor_key": "drive", "order": 2},
    {"key": "concentration", "name": "Concentration", "factor_key": "focus", "order": 0},
    {"key": "presence", "name": "Presence", "factor_key": "focus", "order": 1},
    {"key": "confidence", "name": "Confidence", "factor_key": "mental_toughness", "order": 0},
    {"key": "visualization_ability", "name": "Visualization Ability", "factor_key": "mental_toughness", "order": 1},
    {"key": "stress_management", "name": "Stress Management", "factor_key": "mental_toughness", "order": 2},
    {"key": "sociability", "name": "Sociability", "factor_key": "leadership_potential", "order": 0},
    {"key": "integrity", "name": "Integrity", "factor_key": "leadership_potential", "order": 1},
    {"key": "reliance", "name": "Reliance", "factor_key": "leadership_potential", "order": 2},
    {"key": "team_preference", "name": "Team Preference", "factor_key": "team_orientation", "order": 0},
    {"key": "team_goal_focused", "name": "Team Goal Focused", "factor_key": "team_orientation", "order": 1},
    {"key": "adversity_response", "name": "Adversity Response", "factor_key": "situational_mindsets", "order": 0},
    {"key": "big_moment_performance", "name": "Big Moment Performance", "factor_key": "situational_mindsets", "order": 1},
    {"key": "slump_response", "name": "Slump Response", "factor_key": "situational_mindsets", "order": 2},
    {"key": "criticism_response", "name": "Criticism Response", "factor_key": "situational_mindsets", "order": 3},
    {"key": "teammate_conflict", "name": "Teammate Conflict", "factor_key": "situational_mindsets", "order": 4},
]



def opt(label: str, text: str, score: int, tag: str) -> dict:
    return {"label": label, "text": text, "score": score, "tag": tag, "order": ord(label) - ord("A")}


# --- Questions ---
# order matches the framework doc's Q1..Q40. tier/reverse_scored/question_type/
# measurement_type all come directly from each question's header row in the doc.

QUESTIONS = [
    dict(
        order=1, dimension_key="persistence", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="When I hit a wall in training — physically or mentally — I find a way to push through it.",
        helper_text="Think about the last time practice or training got really hard.",
        options=[
            opt("A", "Strongly Agree — I almost never quit when things get tough.", 5, "Elite Persistence"),
            opt("B", "Agree — I push through most of the time, with occasional setbacks.", 4, "Above Avg"),
            opt("C", "Neutral — It depends on the day and how I'm feeling.", 3, "Average"),
            opt("D", "Disagree — I often find reasons to ease up when it gets hard.", 2, "Below Avg"),
            opt("E", "Strongly Disagree — I struggle to push through difficult training regularly.", 1, "Development Area"),
        ],
    ),
    dict(
        order=2, dimension_key="persistence", question_type="scenario", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="You've been working on the same weakness for 6 weeks. You're not seeing results yet. What do you do?",
        helper_text="Be honest — there's no wrong answer here.",
        options=[
            opt("A", "I keep going. Progress is rarely linear and I trust the process completely.", 5, "Elite Grit"),
            opt("B", "I stay with it but start questioning my approach — maybe I need a different method.", 4, "Strong Grit"),
            opt("C", "I take a short break and revisit it — I need to reset mentally.", 3, "Average Grit"),
            opt("D", "I start spending less time on it and more time on things I'm already good at.", 2, "Avoidance Pattern"),
            opt("E", "I move on. If something isn't working after 6 weeks, it's probably not for me.", 1, "Low Persistence"),
        ],
    ),
    dict(
        order=3, dimension_key="intrinsic_motivation", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="I would train hard even if no coach, parent, or teammate was watching.",
        helper_text="Think about your internal drive — not what others expect of you.",
        options=[
            opt("A", "Strongly Agree — I train for myself, full stop.", 5, "High Intrinsic Drive"),
            opt("B", "Agree — My internal drive is strong, though recognition helps.", 4, "Above Avg"),
            opt("C", "Neutral — I need some external push to stay consistent.", 3, "Mixed Motivation"),
            opt("D", "Disagree — External motivation (coaches, parents, scouts) drives most of my effort.", 2, "Extrinsic Dependent"),
            opt("E", "Strongly Disagree — Without external pressure, I would train much less.", 1, "Low Intrinsic Drive"),
        ],
    ),
    dict(
        order=4, dimension_key="intrinsic_motivation", question_type="likert", measurement_type="state",
        tier="free", reverse_scored=False,
        prompt="Right now, in this moment of your season or training cycle, how motivated do you feel?",
        helper_text="This is about TODAY — not how you usually feel.",
        options=[
            opt("A", "Extremely motivated — I feel locked in and hungry right now.", 5, "High State Motivation"),
            opt("B", "Pretty motivated — I'm engaged and working hard.", 4, "Above Avg State"),
            opt("C", "Moderately motivated — Going through the motions some days.", 3, "Average State"),
            opt("D", "Low motivation right now — I'm grinding but not feeling it.", 2, "State Dip"),
            opt("E", "Very low — I'm struggling to care about training at the moment.", 1, "Burnout Risk"),
        ],
    ),
    dict(
        order=5, dimension_key="extrinsic_motivation", question_type="scenario", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="Your coach tells you that a scout will be watching your next three games/matches. How does this change your preparation?",
        helper_text=None,
        options=[
            opt("A", "It doesn't change much — I prepare the same way every time regardless of who's watching.", 5, "Stable Intrinsic"),
            opt("B", "I prepare slightly more intensely — the external motivation gives me an extra boost.", 4, "Healthy Extrinsic Use"),
            opt("C", "I significantly ramp up preparation — this is a huge opportunity and I treat it differently.", 3, "Opportunity Responsive"),
            opt("D", "I become anxious and my preparation gets disrupted by thinking about the scout.", 2, "Performance Anxiety Risk"),
            opt("E", "I struggle to prepare normally — the pressure overwhelms my routine.", 1, "High Anxiety Pattern"),
        ],
        sport_category_overrides={
            "individual": "Your coach tells you that a scout will be watching your next three races/matches, tracking your times/rankings closely. How does this change your preparation?",
            "combat": "Your coach tells you that a scout will be watching your next three fights, evaluating your ranking. How does this change your preparation?",
        },
    ),
    dict(
        order=6, dimension_key="engagement", question_type="likert", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="I am fully present and mentally engaged during practice — not just going through the motions.",
        helper_text="Be honest. Even elite athletes have days where they check out.",
        options=[
            opt("A", "Strongly Agree — I treat every rep in practice like it matters.", 5, "Elite Engagement"),
            opt("B", "Agree — Most of the time I'm locked in at practice.", 4, "High Engagement"),
            opt("C", "Neutral — My engagement varies a lot depending on what we're doing.", 3, "Inconsistent"),
            opt("D", "Disagree — I find myself going through the motions more often than not.", 2, "Low Engagement"),
            opt("E", "Strongly Disagree — Practice feels like something I have to get through, not something I invest in.", 1, "Disengaged"),
        ],
    ),
    dict(
        order=7, dimension_key="work_ethic", question_type="scenario", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="Practice is over. Your coach hasn't required anything extra. What do you actually do?",
        helper_text=None,
        options=[
            opt("A", "I stay and work on specific weaknesses I identified during practice.", 5, "Elite Work Ethic"),
            opt("B", "I do a little extra on my own — some additional reps or conditioning.", 4, "High Work Ethic"),
            opt("C", "I head home but think about what I should be working on.", 3, "Average"),
            opt("D", "I leave — practice is practice, rest is rest.", 2, "Minimum Effort"),
            opt("E", "I leave as soon as possible — recovery and rest are my priority.", 1, "Low Voluntary Effort"),
        ],
        sport_category_overrides={
            "individual": "Training is over. No one required anything extra of you. What do you actually do?",
            "combat": "The session is over. Your coach hasn't required any extra drilling or sparring. What do you actually do?",
        },
    ),
    dict(
        order=8, dimension_key="work_ethic", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="The effort I put into the details of my sport — film study, nutrition, sleep, recovery — is something I genuinely invest in.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — The details are where championships are made.", 5, "Elite Preparation"),
            opt("B", "Agree — I take the details seriously, though not perfectly.", 4, "High Preparation"),
            opt("C", "Neutral — I handle some details but not all of them consistently.", 3, "Selective"),
            opt("D", "Disagree — I mostly focus on the physical side and less on the details.", 2, "Surface Level"),
            opt("E", "Strongly Disagree — I don't think the details make that big a difference.", 1, "Low Detail Orientation"),
        ],
    ),
    dict(
        order=9, dimension_key="growth_mindset", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="When I fail at something in my sport, my first instinct is to figure out what I can learn from it.",
        helper_text="Think about a recent failure or setback.",
        options=[
            opt("A", "Strongly Agree — Failure is data. I dissect it and move forward.", 5, "Elite Growth Mindset"),
            opt("B", "Agree — I try to learn from failures, though it takes me some time.", 4, "Growth Oriented"),
            opt("C", "Neutral — Sometimes I reflect, sometimes I just move on.", 3, "Mixed Mindset"),
            opt("D", "Disagree — My first instinct is frustration and it takes a while to find the lesson.", 2, "Fixed Tendency"),
            opt("E", "Strongly Disagree — Failure usually just makes me feel like I'm not cut out for this.", 1, "Fixed Mindset"),
        ],
    ),
    dict(
        order=10, dimension_key="growth_mindset", question_type="scenario", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="A teammate or competitor who you used to be better than has clearly surpassed you. What's your honest reaction?",
        helper_text=None,
        options=[
            opt("A", "I'm genuinely motivated by it — it raises the bar for what I know I can achieve.", 5, "Elite Growth Response"),
            opt("B", "I'm frustrated at first but quickly use it as motivation to push harder.", 4, "Healthy Competitive Growth"),
            opt("C", "I feel a mix of inspiration and insecurity — I'm not sure how to process it.", 3, "Mixed Response"),
            opt("D", "It bothers me more than it motivates me — I start questioning my own ability.", 2, "Threat Response"),
            opt("E", "It makes me feel like maybe I've reached my ceiling in this sport.", 1, "Fixed Mindset Trigger"),
        ],
    ),
    dict(
        order=11, dimension_key="goal_orientation_practice", question_type="likert", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="Before practice, I have a clear goal for what I want to improve or accomplish in that session.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — I set specific goals before every practice.", 5, "Elite Goal Setting"),
            opt("B", "Agree — I usually have a sense of what I want to work on.", 4, "Goal Oriented"),
            opt("C", "Neutral — I sometimes set goals but mostly just react to what practice brings.", 3, "Reactive"),
            opt("D", "Disagree — I mostly show up and do what the coach asks without additional personal goals.", 2, "Low Self-Direction"),
            opt("E", "Strongly Disagree — I don't think pre-practice goal setting makes a real difference.", 1, "No Goal Orientation"),
        ],
    ),
    dict(
        order=12, dimension_key="feedback_acceptance", question_type="scenario", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="Your coach corrects the same mistake you've made three times in a row — loudly, in front of your teammates. Your reaction?",
        helper_text="Be honest. This is a safe space.",
        options=[
            opt("A", "I listen, acknowledge it, and make the correction immediately without any defensiveness.", 5, "Elite Coachability"),
            opt("B", "It stings a little, but I focus on fixing the mistake rather than how it was delivered.", 4, "High Coachability"),
            opt("C", "I feel embarrassed but try not to let it affect my performance.", 3, "Average Coachability"),
            opt("D", "I get defensive internally and it takes me a while to let it go.", 2, "Defensive Pattern"),
            opt("E", "I shut down. Public corrections throw me off and make it hard to perform.", 1, "Low Feedback Tolerance"),
        ],
        sport_category_overrides={
            "individual": "Your coach corrects the same mistake you've made three times in a row — bluntly, one-on-one. Your reaction?",
            "combat": "Your corner corrects the same mistake you've made three times in a row — bluntly, between rounds. Your reaction?",
        },
    ),
    dict(
        order=13, dimension_key="feedback_acceptance", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="When a coach gives me critical feedback, I genuinely believe it's making me better — even when it's uncomfortable.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — Critical feedback is the fastest path to improvement.", 5, "Elite Receptivity"),
            opt("B", "Agree — I value critical feedback even when it's hard to hear.", 4, "High Receptivity"),
            opt("C", "Neutral — It depends on how the feedback is delivered.", 3, "Conditional Receptivity"),
            opt("D", "Disagree — I often feel critical feedback is more discouraging than helpful.", 2, "Low Receptivity"),
            opt("E", "Strongly Disagree — Critical feedback usually just makes me feel attacked.", 1, "Defensive"),
        ],
    ),
    dict(
        order=14, dimension_key="humility", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=True,
        prompt="I sometimes feel like I know better than my coach about what I should be doing.",
        helper_text="This is a reverse-scored question — honesty matters most here.",
        options=[
            opt("A", "Strongly Disagree — My coaches have earned my trust and I defer to their expertise.", 5, "High Humility"),
            opt("B", "Disagree — I rarely second-guess my coach's decisions.", 4, "Above Avg Humility"),
            opt("C", "Neutral — Sometimes I agree, sometimes I think I know better.", 3, "Average"),
            opt("D", "Agree — I often feel my judgment about my own development is better than my coach's.", 2, "Low Humility"),
            opt("E", "Strongly Agree — I frequently think my coach's approach is wrong for me.", 1, "Entitlement Pattern"),
        ],
    ),
    dict(
        order=15, dimension_key="humility", question_type="scenario", measurement_type="state",
        tier="elite", reverse_scored=True,
        prompt="You've been performing well this season. Your coach makes a decision that you strongly disagree with — one that directly affects your role. What do you do?",
        helper_text=None,
        options=[
            opt("A", "I have a respectful private conversation with the coach, share my perspective, then fully commit to their decision.", 5, "Elite Humility + Leadership"),
            opt("B", "I accept the decision even if I disagree — I trust the process.", 4, "High Humility"),
            opt("C", "I privately vent to a teammate but ultimately go along with it.", 3, "Average — social processing"),
            opt("D", "I make it clear I disagree and my performance reflects my frustration.", 2, "Low Humility"),
            opt("E", "I become disruptive — it's hard for me to commit when I think a decision is wrong.", 1, "Entitlement / Disruptive"),
        ],
        sport_category_overrides={
            "individual": "You've been performing well this season. Your coach makes a decision you strongly disagree with — one that directly affects your event selection or seeding. What do you do?",
            "combat": "You've been performing well this season. Your coach makes a decision you strongly disagree with — one that directly affects your fight card placement. What do you do?",
        },
    ),
    dict(
        order=16, dimension_key="adherence_to_direction", question_type="likert", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="When a coach gives me a specific instruction — even if it feels counterintuitive — I follow it completely before deciding whether it works.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — I give the instruction a full and honest trial before evaluating it.", 5, "High Adherence"),
            opt("B", "Agree — I usually follow instructions closely, with occasional personal adjustments.", 4, "Above Avg"),
            opt("C", "Neutral — I follow the spirit of instructions but sometimes modify based on feel.", 3, "Selective Adherence"),
            opt("D", "Disagree — I adapt instructions to fit what feels natural to me.", 2, "Low Adherence"),
            opt("E", "Strongly Disagree — I've learned what works for me and I adjust accordingly.", 1, "Resistant"),
        ],
    ),
    dict(
        order=17, dimension_key="entitlement", question_type="scenario", measurement_type="trait",
        tier="elite", reverse_scored=True,
        prompt="You've had a great season. A less experienced teammate gets an opportunity you believe you earned. Your response?",
        helper_text="There's no judgment here — this tests how you process fairness.",
        options=[
            opt("A", "I congratulate them genuinely and keep working — opportunities come from performance.", 5, "Low Entitlement"),
            opt("B", "I'm disappointed internally but don't let it affect my attitude or effort.", 4, "Mature Response"),
            opt("C", "I'm frustrated and need a day or two to process it before refocusing.", 3, "Average"),
            opt("D", "I openly express frustration to my coach and peers — I deserve to know why.", 2, "Entitlement Pattern"),
            opt("E", "It significantly affects my effort and attitude until I feel the situation is corrected.", 1, "High Entitlement"),
        ],
        sport_category_overrides={
            "individual": "You've had a great season. A less experienced athlete gets a wild card or event selection you believe you earned. Your response?",
            "combat": "You've had a great season. A less experienced fighter gets a fight card placement you believe you earned. Your response?",
        },
    ),
    dict(
        order=18, dimension_key="competitiveness", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="Losing genuinely bothers me — not in a destructive way, but in a way that drives me to compete harder next time.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — I hate losing more than I love winning and it fuels my training.", 5, "Elite Competitive Drive"),
            opt("B", "Agree — I take losses seriously and they motivate me.", 4, "High Competitiveness"),
            opt("C", "Neutral — Losing is part of sports. I process it and move forward.", 3, "Average"),
            opt("D", "Disagree — I'm competitive in the moment but losses don't linger for me.", 2, "Low Competitive Burn"),
            opt("E", "Strongly Disagree — Losing doesn't bother me much — I focus on how I played.", 1, "Low Competitiveness"),
        ],
    ),
    dict(
        order=19, dimension_key="competitiveness", question_type="scenario", measurement_type="state",
        tier="free", reverse_scored=False,
        prompt="You are down at halftime / halfway through the match / between rounds. What happens inside you?",
        helper_text="Pick the answer that most honestly describes your internal experience.",
        options=[
            opt("A", "I get more focused and locked in — being down activates something in me.", 5, "Clutch Response"),
            opt("B", "I stay calm and remind myself there's plenty of time / rounds left.", 4, "Composed Competitor"),
            opt("C", "I feel pressure but try to stay positive and keep competing.", 3, "Average Competitive State"),
            opt("D", "I start to worry about whether we can come back / whether I can win.", 2, "Anxiety in Deficit"),
            opt("E", "Being down significantly affects my performance — I struggle to find my game.", 1, "Deficit Shutdown"),
        ],
        sport_category_overrides={
            "team": "You are down at halftime. What happens inside you?",
            "individual": "You are down halfway through the race, or behind by a set or a few holes. What happens inside you?",
            "combat": "You are down on the scorecards between rounds. What happens inside you?",
        },
    ),
    dict(
        order=20, dimension_key="intensity", question_type="likert", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="I bring an intensity and energy to competition that teammates, coaches, or opponents can feel.",
        helper_text="Not arrogance — genuine competitive energy.",
        options=[
            opt("A", "Strongly Agree — People know when I'm locked in. My energy changes the environment.", 5, "Elite Intensity"),
            opt("B", "Agree — I bring strong energy, especially in big moments.", 4, "High Intensity"),
            opt("C", "Neutral — My intensity is steady but not particularly contagious.", 3, "Average"),
            opt("D", "Disagree — I compete internally but don't outwardly project much intensity.", 2, "Internal Only"),
            opt("E", "Strongly Disagree — I perform best when I stay calm and low-key.", 1, "Low External Intensity"),
        ],
    ),
    dict(
        order=21, dimension_key="goal_orientation_performance", question_type="scenario", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="Before a competition, what is your primary focus?",
        helper_text="Choose what's most true — not what sounds best.",
        options=[
            opt("A", "Executing my process — the result will take care of itself if I do my job.", 5, "Process Mastery"),
            opt("B", "Winning — I want to beat the opponent in front of me.", 4, "Performance Goal"),
            opt("C", "My personal stats and performance metrics.", 3, "Ego Goal"),
            opt("D", "Not making mistakes that cost the team.", 2, "Avoidance Orientation"),
            opt("E", "Just getting through it without embarrassing myself.", 1, "Fear-Based Orientation"),
        ],
    ),
    dict(
        order=22, dimension_key="concentration", question_type="scenario", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="It's the most critical moment of the game/match/race. The crowd is loud, the stakes are high. Where is your mind?",
        helper_text=None,
        options=[
            opt("A", "100% on the task — external noise literally disappears for me in these moments.", 5, "Elite Focus"),
            opt("B", "Mostly on the task — I'm aware of the environment but it doesn't distract me.", 4, "High Focus"),
            opt("C", "I'm focused but the environment creeps in and I have to actively manage it.", 3, "Average Focus"),
            opt("D", "The environment significantly affects my concentration in high-stakes moments.", 2, "Focus Vulnerable"),
            opt("E", "High-stakes moments actually make it harder for me to concentrate.", 1, "Pressure Focus Collapse"),
        ],
        position_overrides={
            "Quarterback": "It's the two-minute drill, the crowd is deafening, and the defense is disguising its look. Where is your mind?",
            "Goalkeeper": "It's a breakaway or a penalty shot with the game on the line and the crowd roaring. Where is your mind?",
            "Pitcher": "Bases loaded, full count, the game on the line. Where is your mind?",
        },
    ),
    dict(
        order=23, dimension_key="concentration", question_type="likert", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="After making a mistake during competition, I refocus quickly without letting it affect my next play/action.",
        helper_text="The ability to reset is one of the most critical mental skills in sport.",
        options=[
            opt("A", "Strongly Agree — I have a reset routine and it works. Mistakes don't linger.", 5, "Elite Reset Ability"),
            opt("B", "Agree — I recover fairly quickly, usually within a play or two.", 4, "High Reset"),
            opt("C", "Neutral — It depends on the mistake and how big the moment is.", 3, "Contextual Reset"),
            opt("D", "Disagree — Mistakes stay with me longer than I'd like during competition.", 2, "Slow Reset"),
            opt("E", "Strongly Disagree — One bad play or moment can unravel my whole performance.", 1, "Error Snowball Pattern"),
        ],
    ),
    dict(
        order=24, dimension_key="presence", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="During competition, I am able to stay in the current moment rather than thinking about past mistakes or future outcomes.",
        helper_text="Present-moment awareness is one of the core findings from flow state research (Csikszentmihalyi).",
        options=[
            opt("A", "Strongly Agree — I live in the current play/moment during competition.", 5, "Elite Presence"),
            opt("B", "Agree — I stay present most of the time.", 4, "High Presence"),
            opt("C", "Neutral — My mind wanders between past and future sometimes.", 3, "Average Presence"),
            opt("D", "Disagree — I often find myself thinking about past mistakes or future scenarios mid-competition.", 2, "Low Presence"),
            opt("E", "Strongly Disagree — Past mistakes and future worries significantly occupy my mind during competition.", 1, "Rumination Pattern"),
        ],
    ),
    dict(
        order=25, dimension_key="presence", question_type="scenario", measurement_type="state",
        tier="elite", reverse_scored=False,
        prompt="Think about your LAST competition. How present were you throughout it?",
        helper_text="This measures your current state, not your general tendency.",
        options=[
            opt("A", "Completely present — I was in a flow state for most of it.", 5, "Recent Flow State"),
            opt("B", "Mostly present — I had some mental wandering but stayed competitive.", 4, "High State Presence"),
            opt("C", "Somewhat present — I had periods of distraction that I had to manage.", 3, "Mixed State"),
            opt("D", "Frequently distracted — I was in my head for a lot of the competition.", 2, "Low State Presence"),
            opt("E", "Barely present — I was going through the motions mentally.", 1, "Disengaged State"),
        ],
    ),
    dict(
        order=26, dimension_key="confidence", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="When the game is on the line, I WANT to be the one who has to make the play.",
        helper_text="Think about the biggest moments in your athletic career.",
        options=[
            opt("A", "Strongly Agree — Big moments are what I train for. Give me the ball.", 5, "Clutch Confidence"),
            opt("B", "Agree — I welcome big moments, though I feel the pressure.", 4, "High Confidence"),
            opt("C", "Neutral — I'm okay in big moments but don't specifically seek them out.", 3, "Average Confidence"),
            opt("D", "Disagree — I prefer not to be in the spotlight when it's on the line.", 2, "Pressure Avoidance"),
            opt("E", "Strongly Disagree — High-pressure moments are where I struggle most.", 1, "Pressure Vulnerability"),
        ],
    ),
    dict(
        order=27, dimension_key="confidence", question_type="likert", measurement_type="state",
        tier="free", reverse_scored=False,
        prompt="Right now, how confident do you feel in your ability to perform at your highest level?",
        helper_text="This is a snapshot of TODAY — not your usual level of confidence.",
        options=[
            opt("A", "Extremely confident — I feel unbeatable right now.", 5, "Peak Confidence State"),
            opt("B", "Confident — I trust my preparation and abilities.", 4, "High State Confidence"),
            opt("C", "Moderately confident — I have some doubts but mostly believe in myself.", 3, "Average State"),
            opt("D", "Low confidence right now — I'm second-guessing myself a lot.", 2, "Confidence Dip"),
            opt("E", "Very low — I'm struggling to believe in my ability at the moment.", 1, "Confidence Crisis"),
        ],
    ),
    dict(
        order=28, dimension_key="visualization_ability", question_type="likert", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="I use mental imagery before competition — vividly picturing myself executing at my best — as part of my regular preparation.",
        helper_text="Visualization is one of the 6 core mental skills (Bell, Orlick, Vealey).",
        options=[
            opt("A", "Strongly Agree — Mental rehearsal is a consistent, detailed part of my prep.", 5, "Elite Visualization"),
            opt("B", "Agree — I visualize, though not as consistently or vividly as I could.", 4, "Above Avg"),
            opt("C", "Neutral — I've tried it but I'm not sure how effective it is for me.", 3, "Emerging Skill"),
            opt("D", "Disagree — I rarely use visualization as a preparation tool.", 2, "Underdeveloped"),
            opt("E", "Strongly Disagree — I don't think visualization helps me perform better.", 1, "Visualization Skeptic"),
        ],
    ),
    dict(
        order=29, dimension_key="visualization_ability", question_type="scenario", measurement_type="state",
        tier="elite", reverse_scored=False,
        prompt="Close your eyes for 10 seconds and picture yourself executing perfectly in your next competition. What happens?",
        helper_text="Describe your experience:",
        options=[
            opt("A", "I see it clearly and vividly — the environment, my body, the execution.", 5, "Elite Imagery Vividness"),
            opt("B", "I get a fairly clear picture but some details are fuzzy.", 4, "High Imagery"),
            opt("C", "I can picture it somewhat, but it's more conceptual than vivid.", 3, "Moderate Imagery"),
            opt("D", "I struggle to maintain a clear mental picture.", 2, "Low Imagery"),
            opt("E", "I don't really see anything — mental imagery is difficult for me.", 1, "Imagery Deficit"),
        ],
        position_overrides={
            "Quarterback": "Close your eyes for 10 seconds and picture yourself calling and executing the winning play. What happens?",
            "Goalkeeper": "Close your eyes for 10 seconds and picture yourself making the diving save that wins the game. What happens?",
            "Pitcher": "Close your eyes for 10 seconds and picture yourself throwing the exact pitch you want, right where you want it. What happens?",
        },
    ),
    dict(
        order=30, dimension_key="stress_management", question_type="scenario", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="In the hours before a major competition, how do you experience and manage pre-competition nerves?",
        helper_text=None,
        options=[
            opt("A", "I channel nerves as energy — they make me sharper and more focused.", 5, "Elite Arousal Control"),
            opt("B", "I have nerves but they don't interfere — I've learned to manage them.", 4, "High Stress Management"),
            opt("C", "I feel significant nerves and manage them with varying success.", 3, "Average"),
            opt("D", "Pre-competition nerves often hurt my early performance.", 2, "Anxiety Vulnerability"),
            opt("E", "Pre-competition anxiety is one of my biggest performance challenges.", 1, "High Pre-Comp Anxiety"),
        ],
        sport_category_overrides={
            "individual": "In the hours before a big race or match, how do you experience and manage pre-competition nerves?",
            "combat": "In the hours before a fight, how do you experience and manage pre-fight nerves?",
        },
    ),
    dict(
        order=31, dimension_key="sociability", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="I naturally build strong relationships with teammates and coaches — people are drawn to me as a teammate.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — I'm a connector. People trust me and come to me.", 5, "Elite Sociability"),
            opt("B", "Agree — I build good relationships, though it takes me some time.", 4, "High Sociability"),
            opt("C", "Neutral — I'm friendly but not particularly a social leader.", 3, "Average"),
            opt("D", "Disagree — I prefer to let my performance speak and don't seek deep relationships.", 2, "Reserved"),
            opt("E", "Strongly Disagree — I keep to myself and find team social dynamics draining.", 1, "Lone Wolf Pattern"),
        ],
        sport_category_overrides={
            "individual": "I naturally build strong relationships with my training partners and coaches — people are drawn to me.",
            "combat": "I naturally build strong relationships with my team and corner — people are drawn to me.",
        },
    ),
    dict(
        order=32, dimension_key="integrity", question_type="scenario", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="A teammate is doing something that violates team rules when no coach is around. What do you do?",
        helper_text=None,
        options=[
            opt("A", "I address it directly with the teammate — I hold the standard even when it's uncomfortable.", 5, "Elite Integrity"),
            opt("B", "I tell them I'm not comfortable with it and ask them to stop.", 4, "High Integrity"),
            opt("C", "I remove myself from the situation but don't say anything.", 3, "Passive Integrity"),
            opt("D", "I go along with it to avoid conflict — it's not my place to police teammates.", 2, "Social Compliance"),
            opt("E", "I participate — if everyone's doing it, the group norm matters more.", 1, "Low Integrity"),
        ],
    ),
    dict(
        order=33, dimension_key="reliance", question_type="likert", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="My teammates know that when I say I'll do something, it gets done.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — I'm the person people count on. I never leave commitments unmet.", 5, "Elite Reliability"),
            opt("B", "Agree — I follow through consistently, with rare exceptions.", 4, "High Reliability"),
            opt("C", "Neutral — I intend to follow through but sometimes fall short.", 3, "Average"),
            opt("D", "Disagree — I struggle with consistency in follow-through.", 2, "Low Reliability"),
            opt("E", "Strongly Disagree — I'm better at being in the moment than following through on commitments.", 1, "Unreliable Pattern"),
        ],
    ),
    dict(
        order=34, dimension_key="team_preference", question_type="likert", measurement_type="trait",
        tier="free", reverse_scored=False,
        prompt="I perform better and feel more motivated when my success contributes to a team outcome.",
        helper_text=None,
        options=[
            opt("A", "Strongly Agree — Team wins mean more to me than individual achievements.", 5, "High Team Preference"),
            opt("B", "Agree — I love winning together, though individual achievement also drives me.", 4, "Team Oriented"),
            opt("C", "Neutral — I value both team and individual outcomes equally.", 3, "Balanced"),
            opt("D", "Disagree — Individual achievement motivates me more than team outcomes.", 2, "Individual Preference"),
            opt("E", "Strongly Disagree — I perform best when competing for myself.", 1, "Individual Only"),
        ],
        sport_category_overrides={
            "individual": "I perform better and feel more motivated when my success contributes to my training group or relay team's outcome.",
            "combat": "I perform better and feel more motivated when my success contributes to my team or camp's outcome.",
        },
    ),
    dict(
        order=35, dimension_key="team_goal_focused", question_type="scenario", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="Your individual performance is outstanding but the team is struggling. Your coach asks you to change your role to help the team — it will likely hurt your personal stats. What's your response?",
        helper_text=None,
        options=[
            opt("A", "No hesitation — team first, always. I make the change immediately.", 5, "Elite Team Focus"),
            opt("B", "I commit to it even though it's frustrating. The team comes first.", 4, "High Team Focus"),
            opt("C", "I agree but struggle internally with the impact on my individual performance.", 3, "Team Leaning"),
            opt("D", "I'd want to discuss it with the coach — I think my individual performance helps the team more.", 2, "Individual Leaning"),
            opt("E", "I resist. My individual performance is my biggest contribution to the team.", 1, "Individual Priority"),
        ],
        sport_category_overrides={
            "individual": "Your individual performance is outstanding, but your coach asks you to adjust your training style or event focus to better support your training group — it will likely cost you some personal results. What's your response?",
            "combat": "Your individual performance is outstanding, but your corner asks you to follow a fight strategy that conflicts with your natural style, for the good of the long-term game plan. What's your response?",
        },
    ),
    dict(
        order=36, dimension_key="adversity_response", question_type="scenario", measurement_type="state",
        tier="free", reverse_scored=False,
        prompt="Your team is down by 3 with 5 minutes left / You're down a set / You lost the first two rounds. What do you actually feel and do?",
        helper_text="This is a situational mindset question — it captures how you respond in adversity, not how you think you should respond.",
        options=[
            opt("A", "I get completely locked in — adversity is where I'm at my best.", 5, "Adversity Activated"),
            opt("B", "I feel pressure but use it productively — it sharpens me.", 4, "Pressure Converter"),
            opt("C", "I stay calm and keep competing — results take care of themselves.", 3, "Composed"),
            opt("D", "I feel the weight of the situation and it affects my play.", 2, "Pressure Affected"),
            opt("E", "Deficit situations are where I struggle most — it's hard to reset.", 1, "Adversity Shutdown"),
        ],
        sport_category_overrides={
            "team": "Your team is down by a few points/goals with 5 minutes left. What do you actually feel and do?",
            "individual": "You're down a set, or well behind in the race with laps to go. What do you actually feel and do?",
            "combat": "You lost the first two rounds on the scorecards. What do you actually feel and do?",
        },
    ),
    dict(
        order=37, dimension_key="big_moment_performance", question_type="scenario", measurement_type="state",
        tier="free", reverse_scored=False,
        prompt="The biggest moment of the game is here — the final drive, the penalty kick, the championship round. Your honest experience?",
        helper_text=None,
        options=[
            opt("A", "I feel totally alive. This is exactly what I train for and I perform my best.", 5, "Clutch Performer"),
            opt("B", "I feel the weight of the moment but rise to it most of the time.", 4, "Pressure Riser"),
            opt("C", "I give everything I have — results vary but my effort is always there.", 3, "Effort Consistent"),
            opt("D", "Big moments tend to expose my weaknesses — I want to perform but often fall short.", 2, "Choke Tendency"),
            opt("E", "Big moments are where I'm at my worst. The pressure gets to me.", 1, "Pressure Collapse"),
        ],
        sport_category_overrides={
            "individual": "The biggest moment is here — the final hole, the final heat, the championship match point. Your honest experience?",
            "combat": "The biggest moment is here — the championship round. Your honest experience?",
        },
        position_overrides={
            "Quarterback": "It's the final drive of the championship game, two minutes on the clock. Your honest experience?",
            "Goalkeeper": "It's a penalty kick to decide the championship. Your honest experience?",
        },
    ),
    dict(
        order=38, dimension_key="slump_response", question_type="scenario", measurement_type="state",
        tier="elite", reverse_scored=False,
        prompt="You've been in a performance slump for 2–3 weeks. Nothing you try seems to be working. What defines your response?",
        helper_text=None,
        options=[
            opt("A", "I go back to basics, trust my process, and maintain belief — slumps are part of sport.", 5, "Resilient Slump Response"),
            opt("B", "I seek help — coaches, mentors, film — and actively work the problem.", 4, "Problem-Solving Response"),
            opt("C", "I train harder and hope volume fixes it.", 3, "Effort Response"),
            opt("D", "I start questioning my fundamentals and get caught in analysis paralysis.", 2, "Overthinking Pattern"),
            opt("E", "Slumps spiral for me — they affect my confidence in other areas of my life.", 1, "Slump Contagion"),
        ],
    ),
    dict(
        order=39, dimension_key="criticism_response", question_type="scenario", measurement_type="state",
        tier="elite", reverse_scored=False,
        prompt="Critics — fans, media, or social media — are publicly questioning your ability or worth. How does it affect you?",
        helper_text=None,
        options=[
            opt("A", "It doesn't get in. I know who I am and what I'm capable of.", 5, "Unaffected"),
            opt("B", "I notice it but use it as fuel rather than letting it diminish me.", 4, "Fuel Response"),
            opt("C", "It bothers me temporarily but I compartmentalize it when competing.", 3, "Managed Impact"),
            opt("D", "External criticism significantly affects my confidence and focus.", 2, "External Dependency"),
            opt("E", "Public criticism can unravel my performance for extended periods.", 1, "High External Vulnerability"),
        ],
        sport_category_overrides={
            "individual": "Critics — fans, media, or social media — are publicly questioning your ability. How does it affect you?",
            "combat": "Doubters are publicly questioning whether you belong in the ring/cage before a big fight. How does it affect you?",
        },
    ),
    dict(
        order=40, dimension_key="teammate_conflict", question_type="scenario", measurement_type="trait",
        tier="elite", reverse_scored=False,
        prompt="There's real tension between you and a key teammate — unresolved conflict that's affecting both of you. How do you handle it?",
        helper_text=None,
        options=[
            opt("A", "I initiate a direct, respectful conversation. Unresolved conflict costs the team.", 5, "Conflict Leadership"),
            opt("B", "I give it space to cool down and then address it privately.", 4, "Mature Conflict Handling"),
            opt("C", "I focus on my own performance and hope it resolves itself.", 3, "Avoidance — Passive"),
            opt("D", "I vent to other teammates — I need to process it before addressing it.", 2, "Social Processing — Risk"),
            opt("E", "Conflict with teammates significantly affects my performance until it's resolved.", 1, "Conflict Vulnerable"),
        ],
        sport_category_overrides={
            "individual": "There's real tension between you and your training partner or coach — unresolved conflict that's affecting both of you. How do you handle it?",
            "combat": "There's real tension between you and someone in your corner — unresolved conflict that's affecting both of you. How do you handle it?",
        },
    ),
]


async def ensure_seeded() -> None:
    """
    Populate the assessment tables if they're empty, then make sure every
    question's translation content is in sync. Safe to call on every startup:
    the bootstrap insert only runs once, and the content backfill is a cheap
    no-op once nothing is missing.
    """
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(AssessmentPhase.id).limit(1))
        if existing.scalar_one_or_none() is None:
            await _seed_taxonomy_and_questions(db)
            await db.commit()
            print(f"✅ Seeded assessment bank: {len(PHASES)} phases, {len(FACTORS)} factors, "
                  f"{len(DIMENSIONS)} dimensions, {len(QUESTIONS)} questions.")

        await _backfill_missing_question_content(db)


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
            reverse_scored=q["reverse_scored"],
            sport_category_overrides=q.get("sport_category_overrides"),
            position_overrides=q.get("position_overrides"),
        )
        # Appending (rather than a bare db.add with question_id=...) keeps
        # question.options populated in-memory, which the content backfill
        # right after this needs.
        question.options = [AssessmentQuestionOption(**o) for o in q["options"]]
        db.add(question)
    await db.flush()


async def _backfill_missing_question_content(db: AsyncSession) -> None:
    """
    Populate ContentEntry translation rows for any question that doesn't have
    them yet — covers the questions just seeded above on a fresh install, and
    any older data saved before translation support existed.
    """
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


if __name__ == "__main__":
    asyncio.run(ensure_seeded())
