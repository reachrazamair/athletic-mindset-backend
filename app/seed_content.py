"""
SEED CONTENT — load the initial site text into the database.

Run once (and re-run safely) to populate the content table with the English
master strings and their auto-translated versions.

    uv run python -m app.seed_content

Idempotent: existing keys are updated, not duplicated. As we move more pages
into the content system, add their English strings to CONTENT below.
"""

import asyncio

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import ContentEntry

# English master strings, keyed the same way the frontend reads them.
# (Batch 1: full home page.)
CONTENT: dict[str, str] = {
    # Hero
    "home.hero.badge": "Trusted by 5,000+ athletes nationwide",
    "home.hero.titleTop": "We Measure Your",
    "home.hero.titleBottom": "Athletic Mindset",
    "home.hero.subtitle": (
        "The only psychologist-engineered assessment that measures 22 dimensions "
        "of your mental game in 15 minutes. So you can train it."
    ),
    "home.hero.cta": "Take Free Assessment",
    "home.hero.note": "No credit card required · 15 min · Instant results",
    "home.hero.pllPartner": "Official PLL Academy Partner",
    "home.hero.trust1": "Engineered by Psychologists",
    "home.hero.trust2": "Science-Backed",
    "home.hero.trust3": "Used by Universities & Clubs",
    "home.hero.scroll": "Scroll to explore",
    # Stats
    "home.stats.titleA": "The Most Comprehensive Mental",
    "home.stats.titleB": "Performance Assessment",
    "home.stats.subtitle": (
        "Our four-level scoring architecture gives athletes the deepest "
        "understanding of their mental game available anywhere."
    ),
    "home.stats.phases.label": "Phases",
    "home.stats.phases.desc": "Preparation · Competition · Teamwork",
    "home.stats.factors.label": "Factors",
    "home.stats.factors.desc": "Core mental performance drivers",
    "home.stats.dimensions.label": "Dimensions",
    "home.stats.dimensions.desc": "Granular mental skill measures",
    "home.stats.situational.label": "Situational Mindsets",
    "home.stats.situational.desc": "Context-specific mental states",
    # Report preview
    "home.report.eyebrow": "Your Report",
    "home.report.titleA": "See What You'll",
    "home.report.titleB": "Discover",
    "home.report.subtitle": (
        "A snapshot of your personalized mental performance profile. Scored "
        "across 8 factors and 22 dimensions using T-scores."
    ),
    "home.report.scores.mentalToughness": "Mental Toughness",
    "home.report.scores.focus": "Focus",
    "home.report.scores.drive": "Drive",
    "home.report.scores.coachability": "Coachability",
    "home.report.scores.grit": "Grit",
    "home.report.scores.leadership": "Leadership",
    "home.report.scores.workStyle": "Work Style",
    "home.report.scores.teamOrientation": "Team Orientation",
    "home.report.bands.high": "High",
    "home.report.bands.average": "Average",
    "home.report.bands.veryHigh": "Very High",
    "home.report.bands.aboveAverage": "Above Average",
    "home.report.bands.belowAverage": "Below Average",
    "home.report.totalScore": "Total AM Score",
    "home.report.sampleLabel": "Sample Athlete Report",
    "home.report.profileTitle": "Athletic Mindset Profile",
    "home.report.gameplanLabel": "Personalized Gameplan:",
    "home.report.gameplanLine1": (
        "Based on your scores, here are the mental skills routines recommended "
        "for your development..."
    ),
    "home.report.gameplanLine2": (
        "Your primary focus areas are Visualization and Self-Talk techniques "
        "applied to competition pressure scenarios..."
    ),
    "home.report.unlock": "Take the assessment to unlock your full Gameplan",
    "home.report.getReport": "Get My Report",
    # What we measure
    "home.measure.eyebrow": "What We Measure",
    "home.measure.titleA": "Three Phases of",
    "home.measure.titleB": "Mental Performance",
    "home.measure.subtitle": (
        "Every athlete is scored across preparation, competition, and teamwork, "
        "giving a complete picture of mental readiness from training to game day."
    ),
    "home.measure.phases.preparation.name": "Preparation",
    "home.measure.phases.preparation.desc": "How athletes prepare, train, and receive coaching",
    "home.measure.phases.competition.name": "Competition",
    "home.measure.phases.competition.desc": "How athletes perform and compete under pressure",
    "home.measure.phases.teamwork.name": "Teamwork",
    "home.measure.phases.teamwork.desc": "Team contribution, leadership, and situational response",
    "home.measure.factors.workStyle.name": "Work Style",
    "home.measure.factors.workStyle.desc": "Approach to training and practice habits",
    "home.measure.factors.coachability.name": "Coachability",
    "home.measure.factors.coachability.desc": "Receptiveness to feedback and instruction",
    "home.measure.factors.grit.name": "Grit",
    "home.measure.factors.grit.desc": "Perseverance and passion for long-term goals",
    "home.measure.factors.drive.name": "Drive",
    "home.measure.factors.drive.desc": "Internal motivation and competitive desire",
    "home.measure.factors.focus.name": "Focus",
    "home.measure.factors.focus.desc": "Concentration and attention management",
    "home.measure.factors.mentalToughness.name": "Mental Toughness",
    "home.measure.factors.mentalToughness.desc": "Resilience under pressure and adversity",
    "home.measure.factors.leadership.name": "Leadership Potential",
    "home.measure.factors.leadership.desc": "Ability to inspire and guide teammates",
    "home.measure.factors.teamOrientation.name": "Team Orientation",
    "home.measure.factors.teamOrientation.desc": "Collaboration and team-first mentality",
    "home.measure.noteA": "Each factor breaks down into multiple dimensions, totaling",
    "home.measure.noteHighlight": "22 granular measures",
    "home.measure.noteB": "of your mental game.",
    # How it works
    "home.how.eyebrow": "How It Works",
    "home.how.titleA": "From Assessment to",
    "home.how.titleB": "Action",
    "home.how.subtitle": (
        "A clear path from understanding your mental game to actively improving "
        "it, backed by science, guided by experts."
    ),
    "home.how.steps.assess.title": "Take the Assessment",
    "home.how.steps.assess.desc": (
        "Complete our psychologist-designed assessment covering all 22 dimensions "
        "of mental performance. Takes about 15 minutes."
    ),
    "home.how.steps.scores.title": "Get Your Scores",
    "home.how.steps.scores.desc": (
        "Receive your T-scores across all 8 factors, benchmarked against thousands "
        "of athletes. See exactly where you stand."
    ),
    "home.how.steps.gameplan.title": "Read Your Gameplan",
    "home.how.steps.gameplan.desc": (
        "Get a personalized report with actionable steps, written differently for "
        "athletes, parents, and coaches."
    ),
    "home.how.steps.train.title": "Train & Improve",
    "home.how.steps.train.desc": (
        "Follow your mental skills routines, track progress over time, and reassess "
        "to see your growth."
    ),
    # Solutions
    "home.solutions.eyebrow": "Built For Everyone",
    "home.solutions.titleA": "Solutions For Your",
    "home.solutions.titleB": "Entire Team",
    "home.solutions.subtitle": (
        "Same assessment data, different experiences, tailored for each person in "
        "the athlete's support system."
    ),
    "home.solutions.totalScore": "Total AM Score",
    "home.solutions.aboveAverage": "Above Average",
    "home.solutions.getStarted": "Get Started Free",
    "home.solutions.athlete.short": "Athletes",
    "home.solutions.athlete.tagline": "Know your mental game. Own your mental game.",
    "home.solutions.athlete.description": (
        "Get a complete mental performance profile scored across 22 dimensions. "
        "Understand exactly where your strengths are and where to focus your mental "
        "training for the biggest gains."
    ),
    "home.solutions.athlete.features.0": "Personal T-score across all 22 dimensions",
    "home.solutions.athlete.features.1": "Benchmarked against thousands of athletes in your sport",
    "home.solutions.athlete.features.2": "Personalized Gameplan with actionable mental skills",
    "home.solutions.athlete.features.3": "Progress tracking with reassessment over time",
    "home.solutions.athlete.features.4": "Mental training routines tailored to your weak spots",
    "home.solutions.parent.short": "Parents",
    "home.solutions.parent.tagline": "Finally understand what's happening inside your athlete's head.",
    "home.solutions.parent.description": (
        "Get a jargon-free report that helps you support your child's mental "
        "development, without undermining their coach or adding pressure."
    ),
    "home.solutions.parent.features.0": "Simple, clear language, no psychology degree needed",
    "home.solutions.parent.features.1": "Understand your child's mental strengths and growth areas",
    "home.solutions.parent.features.2": "Communication tips to support without adding pressure",
    "home.solutions.parent.features.3": "Progress visibility over time",
    "home.solutions.parent.features.4": "Coaching tips so you know how to help at home",
    "home.solutions.coach.short": "Coaches",
    "home.solutions.coach.tagline": "Coach the whole athlete. Not just the physical.",
    "home.solutions.coach.description": (
        "See your entire roster's mental readiness at a glance. Know which athletes "
        "need attention, who's ready to lead, and how to communicate with each "
        "player based on their profile."
    ),
    "home.solutions.coach.features.0": "Roster-wide mental readiness dashboard",
    "home.solutions.coach.features.1": "Individual athlete reports with coaching language",
    "home.solutions.coach.features.2": "Identify at-risk athletes before performance drops",
    "home.solutions.coach.features.3": "Leadership potential and role recommendations",
    "home.solutions.coach.features.4": "Revenue share, earn from every athlete you bring in",
    "home.solutions.organization.short": "Clubs",
    "home.solutions.organization.tagline": "Scale mental performance across your entire program.",
    "home.solutions.organization.description": (
        "Bulk onboard hundreds or thousands of athletes. Get organization-wide "
        "insights, benchmarking, and a branded experience that elevates your program."
    ),
    "home.solutions.organization.features.0": "Bulk athlete import, CSV, links, or QR codes",
    "home.solutions.organization.features.1": "Organization-wide analytics and benchmarks",
    "home.solutions.organization.features.2": "Dedicated account support",
    "home.solutions.organization.features.3": "Volume pricing with club-level billing",
    # Testimonials
    "home.testimonials.eyebrow": "Testimonials",
    "home.testimonials.titleA": "Real Athletes.",
    "home.testimonials.titleB": "Real Results.",
    "home.testimonials.featured.quote": (
        "On Saturday I took my girls field hockey team to a 1v1 shootout and one of "
        "the players said 'My assessment said I have a hard time under pressure and "
        "this is what I have to do', she was referring to one of the Athletic "
        "Mindset relaxation techniques, and then went out and scored a huge goal for "
        "us. From that moment on the rest of my girls bought into the program. I went "
        "on to be coach of the year, and now all juniors and seniors at Friends "
        "Academy utilize this amazing platform."
    ),
    "home.testimonials.featured.role": "Head Field Hockey Coach",
    "home.testimonials.items.0.quote": (
        "I feel that the assessment is essential in self-reflection, something every "
        "athlete should have to take. It puts your strengths and weaknesses at the "
        "forefront of the mind. It brings feelings into life, into reality."
    ),
    "home.testimonials.items.0.role": "Athlete",
    "home.testimonials.items.1.quote": (
        "This really was very accurate about me. This test helped me show what else "
        "I'm good at but also what I can improve on. I feel like the stuff that it "
        "told me to do will make me a better player."
    ),
    "home.testimonials.items.1.role": "Soccer Player",
    "home.testimonials.items.2.quote": (
        "To be frank, this assessment exposed the horrifying truth on some of my "
        "weaknesses and strengths. I was asked questions that stimulated my mind and "
        "allowed me to look at things from a different aspect."
    ),
    "home.testimonials.items.2.role": "Athlete",
    "home.testimonials.items.3.quote": (
        "The feedback highlights my strengths and weaknesses both extrinsically and "
        "intrinsically. It provides a detailed account of how my personal qualities "
        "measure up to the standards of a typical athlete."
    ),
    "home.testimonials.items.3.role": "Athlete",
    "home.testimonials.items.4.quote": (
        "All of our girls completed their individual assessment. I have LOVED seeing "
        "the individual results! The summary is awesome, very helpful!"
    ),
    "home.testimonials.items.4.role": "Women's Lacrosse Coach",
    # Final CTA
    "home.cta.titleA": "Ready to Discover Your",
    "home.cta.titleB": "Athletic Mindset?",
    "home.cta.subtitle": (
        "Take the free assessment and get your mental performance profile in 15 "
        "minutes. No credit card required."
    ),
    "home.cta.primary": "Take Free Assessment",
    "home.cta.secondary": "Request a Demo",
    "home.cta.stat1": "Free to start",
    "home.cta.stat2": "15 min assessment",
    "home.cta.stat3": "Instant results",
    "home.cta.stat4": "60+ sports supported",
    # --- Athletes page ---
    # Hero
    "athletes.hero.pre": "Don't just know your mental game.",
    "athletes.hero.titleA": "Own It.",
    "athletes.hero.titleB": "So It Doesn't Own You.",
    "athletes.hero.subtitle": (
        "Get your complete mental performance profile, scored across 22 "
        "dimensions, benchmarked against athletes in your sport."
    ),
    "athletes.hero.cta": "Get Your Report",
    "athletes.hero.note": "15-minute assessment · Instant results · Personalized gameplan",
    "athletes.hero.statDimensions": "Dimensions",
    "athletes.hero.statFactors": "Factors",
    "athletes.hero.statPhases": "Phases",
    "athletes.hero.statMinutes": "Minutes",
    # What you get
    "athletes.get.eyebrow": "What You Get",
    "athletes.get.titleA": "Your Complete Mental",
    "athletes.get.titleB": "Performance Profile",
    "athletes.get.subtitle": (
        "One assessment. 15 minutes. A deep, scientific look at the mental side "
        "of your game that no physical test can measure."
    ),
    "athletes.get.features.tscores.title": "T-Scores Across 22 Dimensions",
    "athletes.get.features.tscores.desc": "Every aspect of your mental game scored on a scientific scale, from Focus to Grit to Mental Toughness.",
    "athletes.get.features.gameplan.title": "Personalized Gameplan",
    "athletes.get.features.gameplan.desc": "Actionable development strategies tailored to your weakest areas with specific mental skills routines.",
    "athletes.get.features.situational.title": "Situational Mindset Analysis",
    "athletes.get.features.situational.desc": "7 mindset profiles showing how you perform under pressure, deal with setbacks, and lead your team.",
    "athletes.get.features.benchmark.title": "Sport-Specific Benchmarking",
    "athletes.get.features.benchmark.desc": "See how you stack up against thousands of athletes in your sport, age group, and competition level.",
    "athletes.get.features.elite.title": "Elite Comparison",
    "athletes.get.features.elite.desc": "Compare your scores directly against D1 and professional athletes to see where you stand.",
    "athletes.get.features.routines.title": "Mental Skills Routines",
    "athletes.get.features.routines.desc": "Self-talk, visualization, emotional control, and goal-setting techniques assigned to your specific gaps.",
    # Framework
    "athletes.framework.eyebrow": "The Framework",
    "athletes.framework.titleA": "3 Phases. 8 Factors.",
    "athletes.framework.titleB": "22 Dimensions.",
    "athletes.framework.subtitle": "Every dimension of your mental game mapped, measured, and connected to specific development strategies.",
    "athletes.framework.factorsMeasured": "factors measured",
    "athletes.framework.phases.0.name": "Preparation",
    "athletes.framework.phases.0.tagline": "Building the Foundation",
    "athletes.framework.phases.0.factors.0.name": "Grit",
    "athletes.framework.phases.0.factors.0.desc": "Perseverance and motivation for long-term goals",
    "athletes.framework.phases.0.factors.0.dimensions.0": "Intrinsic Motivation",
    "athletes.framework.phases.0.factors.0.dimensions.1": "Persistence",
    "athletes.framework.phases.0.factors.1.name": "Work Style",
    "athletes.framework.phases.0.factors.1.desc": "Attitude and mindset during practice and preparation",
    "athletes.framework.phases.0.factors.1.dimensions.0": "Mastery Approach",
    "athletes.framework.phases.0.factors.1.dimensions.1": "Growth Mindset",
    "athletes.framework.phases.0.factors.2.name": "Coachability",
    "athletes.framework.phases.0.factors.2.desc": "Receptiveness to learning and feedback",
    "athletes.framework.phases.0.factors.2.dimensions.0": "Cooperation",
    "athletes.framework.phases.0.factors.2.dimensions.1": "Feedback Acceptance",
    "athletes.framework.phases.0.factors.2.dimensions.2": "Modesty",
    "athletes.framework.phases.1.name": "Competition",
    "athletes.framework.phases.1.tagline": "Executing Under Pressure",
    "athletes.framework.phases.1.factors.0.name": "Drive",
    "athletes.framework.phases.1.factors.0.desc": "Short-term motivation to compete and win",
    "athletes.framework.phases.1.factors.0.dimensions.0": "Competitiveness",
    "athletes.framework.phases.1.factors.0.dimensions.1": "Challenge Approach",
    "athletes.framework.phases.1.factors.1.name": "Focus",
    "athletes.framework.phases.1.factors.1.desc": "Maintaining positive concentration during events",
    "athletes.framework.phases.1.factors.1.dimensions.0": "Concentration",
    "athletes.framework.phases.1.factors.1.dimensions.1": "Presence",
    "athletes.framework.phases.1.factors.1.dimensions.2": "Visualization Ability",
    "athletes.framework.phases.1.factors.2.name": "Mental Toughness",
    "athletes.framework.phases.1.factors.2.desc": "Confidence, emotional control, and bouncing back",
    "athletes.framework.phases.1.factors.2.dimensions.0": "Positive Coping Style",
    "athletes.framework.phases.1.factors.2.dimensions.1": "Stress Management",
    "athletes.framework.phases.1.factors.2.dimensions.2": "Confidence",
    "athletes.framework.phases.2.name": "Teamwork",
    "athletes.framework.phases.2.tagline": "Excelling as Part of the Unit",
    "athletes.framework.phases.2.factors.0.name": "Leadership Potential",
    "athletes.framework.phases.2.factors.0.desc": "Ability to elevate others and earn trust",
    "athletes.framework.phases.2.factors.0.dimensions.0": "Integrity",
    "athletes.framework.phases.2.factors.0.dimensions.1": "Assertiveness",
    "athletes.framework.phases.2.factors.1.name": "Team Orientation",
    "athletes.framework.phases.2.factors.1.desc": "Contributing to team success and supporting others",
    "athletes.framework.phases.2.factors.1.dimensions.0": "Team Preference",
    "athletes.framework.phases.2.factors.1.dimensions.1": "Reliance",
    "athletes.framework.phases.2.factors.1.dimensions.2": "Team Goal Focus",
    "athletes.framework.phases.2.factors.1.dimensions.3": "Sociability",
    # Report preview
    "athletes.report.eyebrow": "Report Preview",
    "athletes.report.titleA": "See What Your Report",
    "athletes.report.titleB": "Looks Like",
    "athletes.report.subtitle": "A real snapshot from the Athletic Mindset Athlete Report. Your actual results will be based on your unique assessment responses.",
    "athletes.report.scores.mentalToughness": "Mental Toughness",
    "athletes.report.scores.focus": "Focus",
    "athletes.report.scores.drive": "Drive",
    "athletes.report.scores.coachability": "Coachability",
    "athletes.report.scores.grit": "Grit",
    "athletes.report.scores.leadership": "Leadership",
    "athletes.report.scores.workStyle": "Work Style",
    "athletes.report.scores.teamOrientation": "Team Orientation",
    "athletes.report.bands.high": "High",
    "athletes.report.bands.average": "Average",
    "athletes.report.bands.veryHigh": "Very High",
    "athletes.report.bands.aboveAverage": "Above Average",
    "athletes.report.bands.belowAvg": "Below Avg",
    "athletes.report.totalScore": "Total AM Score",
    "athletes.report.sampleLabel": "Sample Athlete Report",
    "athletes.report.profileTitle": "Athletic Mindset Profile",
    "athletes.report.gameplanLabel": "Your Personalized Gameplan:",
    "athletes.report.gameplanLine1": "Based on your Work Style and Grit scores, your primary mental skills focus should be on Visualization and Goal-Setting routines...",
    "athletes.report.gameplanLine2": "Recommended routine: 5-minute pre-practice visualization focusing on mastery cues. Add daily journaling...",
    "athletes.report.unlock": "Your full Gameplan unlocks with your report",
    "athletes.report.getReport": "Get My Report",
    # How it helps
    "athletes.help.eyebrow": "How It Helps",
    "athletes.help.titleA": "Your Report Helps You",
    "athletes.help.titleB": "Level Up",
    "athletes.help.benefits.0": "Identify areas of your mental approach that require improvement and use suggested strategies to fix them",
    "athletes.help.benefits.1": "Understand the situations in competition that will be most challenging and how to maximize performance",
    "athletes.help.benefits.2": "Learn how to be more effective and efficient with preparation time",
    "athletes.help.benefits.3": "Communicate to scouts and coaches your mental strengths and development plan",
    "athletes.help.benefits.4": "Track progress over time with reassessments to see real growth",
    "athletes.help.benefits.5": "Get specific mental skills routines, Self-talk, Visualization, Emotional Control, Goal Setting",
    # Testimonials
    "athletes.testimonials.eyebrow": "From Real Athletes",
    "athletes.testimonials.titleA": "Athletes Like You",
    "athletes.testimonials.titleB": "Agree",
    "athletes.testimonials.items.0.quote": "This really was very accurate about me. Since I play soccer I've been told by other coaches what my flaws are and one major flaw is that I need to stay calm on the field and concentrate. This test helped me show what else I'm good at but also what I can improve on. I feel like the stuff that it told me to do will make me a better player.",
    "athletes.testimonials.items.0.sport": "Soccer",
    "athletes.testimonials.items.1.quote": "I feel that the assessment is essential in self-reflection, something every athlete should have to take. It puts your strengths and weaknesses at the forefront of the mind. The fact that it puts words to one's behavior and actions is a big deal. It brings feelings into life, into reality.",
    "athletes.testimonials.items.1.sport": "Athlete",
    "athletes.testimonials.items.2.quote": "This assessment exam exposed the truth on some of my weaknesses and strengths. I was asked questions that was stimulating to my mind and allowed me to look at things from a different aspect. The results disclosed characteristics of myself, that I knew I had, but was in denial about.",
    "athletes.testimonials.items.2.sport": "Athlete",
    "athletes.testimonials.items.3.quote": "The feedback I received is informative about highlighting my strengths and weaknesses both extrinsically and intrinsically. It provides a detailed account of how my personal qualities measure up to the standards of a typical athlete, and suggests how I should improve steadily.",
    "athletes.testimonials.items.3.sport": "Athlete",
    # Pricing
    "athletes.pricing.eyebrow": "Pricing",
    "athletes.pricing.titleA": "Invest in Your",
    "athletes.pricing.titleB": "Mental Edge",
    "athletes.pricing.subtitle": "Start free or go all-in with the Elite Report for the full depth of your mental performance profile.",
    "athletes.pricing.monthly": "Monthly",
    "athletes.pricing.yearly": "Yearly",
    "athletes.pricing.save": "Save 15%",
    "athletes.pricing.recommended": "Recommended",
    "athletes.pricing.perYear": "/year",
    "athletes.pricing.billedYearly": "Billed as $125/year",
    "athletes.pricing.unlockWith": "Unlock with Elite",
    "athletes.pricing.note": "Parents purchasing for their athlete: the Elite report includes a separate Parent Gameplan at no extra cost.",
    "athletes.pricing.tiers.free.name": "Free",
    "athletes.pricing.tiers.free.description": "See where you stand, 1 factor unlocked",
    "athletes.pricing.tiers.free.features.0": "Full 22-dimension assessment",
    "athletes.pricing.tiers.free.features.1": "1 factor score unlocked (of 8)",
    "athletes.pricing.tiers.free.features.2": "Overall Athletic Mindset score",
    "athletes.pricing.tiers.free.features.3": "Basic percentile ranking",
    "athletes.pricing.tiers.free.locked.0": "Full 8-factor detailed breakdown",
    "athletes.pricing.tiers.free.locked.1": "Personalized Gameplan",
    "athletes.pricing.tiers.free.locked.2": "Mental skills routines",
    "athletes.pricing.tiers.free.locked.3": "Sport-specific benchmarking",
    "athletes.pricing.tiers.free.cta": "Start Free",
    "athletes.pricing.tiers.elite.name": "Elite Report",
    "athletes.pricing.tiers.elite.description": "The complete mental performance experience",
    "athletes.pricing.tiers.elite.features.0": "Everything in Free, plus:",
    "athletes.pricing.tiers.elite.features.1": "Full detailed report, all 22 dimensions",
    "athletes.pricing.tiers.elite.features.2": "Personalized Gameplan with mental skills",
    "athletes.pricing.tiers.elite.features.3": "Sport-specific benchmarking",
    "athletes.pricing.tiers.elite.features.4": "Elite athlete comparison (D1/Pro)",
    "athletes.pricing.tiers.elite.features.5": "7 Situational Mindset profiles",
    "athletes.pricing.tiers.elite.features.6": "Unlimited reassessments",
    "athletes.pricing.tiers.elite.features.7": "Progress tracking over time",
    "athletes.pricing.tiers.elite.features.8": "Parent & Coach report included",
    "athletes.pricing.tiers.elite.cta": "Get Elite Report",
    # Final CTA
    "athletes.cta.titleA": "Ready to Discover Your",
    "athletes.cta.titleB": "Athletic Mindset?",
    "athletes.cta.subtitle": "15 minutes. 22 dimensions. A personalized gameplan to train your mind like you train your body.",
    "athletes.cta.button": "Get Your Report",
    "athletes.cta.stat1": "Instant results",
    "athletes.cta.stat2": "60+ sports supported",
    "athletes.cta.stat3": "Science-backed",
}


async def _seed_missing(db) -> int:
    """Insert only English keys that don't exist yet; never overwrite edits."""
    master = settings.CONTENT_MASTER_LOCALE
    result = await db.execute(
        select(ContentEntry.key).where(ContentEntry.locale == master)
    )
    existing = {row[0] for row in result.all()}

    added = 0
    for key, value in CONTENT.items():
        if key not in existing:
            db.add(ContentEntry(key=key, locale=master, value=value))
            added += 1
    if added:
        await db.commit()
    return added


async def ensure_seeded() -> None:
    """Auto-seed missing content. Safe to run on every startup and deploy."""
    async with AsyncSessionLocal() as db:
        added = await _seed_missing(db)
    if added:
        print(f"✓ seeded {added} new content string(s)")


async def main() -> None:
    await ensure_seeded()
    print("Done. New languages fill in on first view; existing edits untouched.")


if __name__ == "__main__":
    asyncio.run(main())
