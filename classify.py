"""Decide how important an item is, and say what happened in one sentence.

Three tiers:
  A  Achievement  awards, recognition, grants, funding
  B  Notable      partnerships, government launches, milestones, announcements, media coverage
  C  Routine      hiring, calls for applications, event invitations, festival greetings, programme posts

Rules only (no AI service). Each rule is a list of phrases; add to them when something is missed.
"""
import re

# Posts that are never news about the organisation itself, whatever else they mention.
# "Bhumi Fellowship is inviting applications" is an opportunity being advertised, not a fellowship won.
ROUTINE_RE = re.compile(
    r"#?hiring\b|\b(we('| a)re|is|are) hiring\b|\bvacanc|\bwalk-in\b|\bapply (by|now|here|today)\b|"
    r"\b(inviting|invites|calling for|call for) (applications|nominations|entries|proposals)\b|"
    r"\b(applications?|registrations?|nominations?) (are |is )?(now |still )?(open|closed|invited|live)\b|"
    r"\blast (date|\d+ hours)\b|\bregister (now|here|today)\b|\bjoin us (for|on|at|in)\b|\bwebinar\b|"
    r"\bhappy (diwali|deepavali|holi|eid|christmas|new year|independence day|republic day|children'?s day)\b|"
    r"\bwishing (you|everyone)\b|\btake this poll\b|#rlpoll",
    re.I)

AWARD = re.compile(
    r"\b(awards?|awarded|awardees?|prizes?|winners?|"
    r"(win|wins|won|winning) (the|an?|first|second|third|gold|silver|bronze|big|at|in)|"
    r"finalists?|shortlisted|felicitated|laureates?|conferred|special mention|honou?rable mention|"
    r"troph(y|ies)|accolades?)\b", re.I)
RECOGNITION = re.compile(
    r"\b(recogni[sz]ed (as|by|among|for|with|our|the)|recognition (from|by|for|as)|national recognition|"
    r"honou?red (with|by|to receive|to be)|named (among|in|to|as|one)|"
    r"(selected|chosen|listed|featured|ranked) (as|among|in|for|by) [^.]{0,70}"
    r"(top|one of|best|\d+|cohort|list|fellows?|innovations?|winners?|finalists?)|"
    r"one of (the )?(top |only |five |ten |\d+ )|top \d+|\d+ under \d+)", re.I)
FUNDING = re.compile(
    r"\b(raises?|raised|secures?|secured|receives?|received|awarded|bags?|bagged) [^.]{0,50}"
    r"(funding|seed|round|grants?|crore|lakh|million|\$|₹)|"
    r"\bgrants? (from|of|by|worth)\b|\bthrough the [^.]{0,40}\bgrant\b|\b(funded|backed) by\b|"
    r"\blists? on [^.]{0,40}(stock exchange|sse)\b|\bsocial stock exchange\b|\binvestment from\b", re.I)

PARTNERSHIP = re.compile(
    r"\b(mou|memorandum of understanding|partnership with|partner(ed|ing)? with|to partner with|"
    r"signed (an? )?(agreement|mou|partnership)|tie-?up with|we have (renewed|signed))\b", re.I)
GOVERNMENT = re.compile(
    r"\b(chief minister|hon'?ble|minister|governor|government of \w+|govt\.? of \w+|niti aayog|ministry of|"
    r"state government|district administration|zilla parishad|municipal corporation)\b[^.]{0,140}"
    r"\b(launch\w*|inaugurat\w*|sign\w*|flag\w*|adopt\w*|announc\w*|releas\w*|felicitat\w*|recogni\w*)\b|"
    r"\b(launch\w*|inaugurat\w*|sign\w*|adopt\w*|releas\w*)\b[^.]{0,140}"
    r"\b(chief minister|hon'?ble|minister|governor|government of \w+|govt\.? of \w+|state government)\b", re.I)
MILESTONE = re.compile(
    r"\b(milestone|now reaching|reaching more|is now (in|live|available|reaching)|"
    r"expand(s|ed|ing)? (to|into|our|across)|expansion|scal(e|ed|ing) (to|up|across)|"
    r"launch(ed|es|ing)? (of|in|our|the|a|an)\b|"
    r"(served|reached|crossed|impacted) (over |more than |nearly )?(a |one |[\d,.]+ ?)(lakh|million|crore|k\b|\+)|"
    r"annual report)", re.I)
ANNOUNCEMENT = re.compile(
    r"\b(we('| a)re|we are|i('| a)m|i am) (so |very |truly |deeply |super |incredibly )?"
    r"(humbled|thrilled|delighted|excited|proud|happy|glad|pleased|honou?red)( and \w+)? "
    r"to (share|announce|welcome|introduce|launch|partner|be)\b|"
    r"\bhonou?red to partner\b|\bproud (moment|milestone)\b|\bbig (news|moment)\b", re.I)
MEDIA = re.compile(
    r"\b(featured (in|on|by)|covered by|interview(ed)? (with|by|in|on)|spoke at|speaking at|"
    r"panel(list)? (at|on)|keynote|round ?table|tedx|op-?ed|published in|peace forum|world economic forum)\b",
    re.I)

TIER_A = [("Grant / funding", FUNDING), ("Award / recognition", AWARD), ("Award / recognition", RECOGNITION)]
TIER_B = [("Partnership", PARTNERSHIP), ("Government", GOVERNMENT), ("Milestone / launch", MILESTONE),
          ("Announcement", ANNOUNCEMENT), ("Media / speaking", MEDIA)]
TIER_NAMES = {"A": "Achievement", "B": "Notable", "C": "Routine"}
NEWS = ("Google News", "Bing News")

LEAD_IN = re.compile(
    r"^(a |what a )?(proud|big|huge|special) (moment|milestone|day|news)[^.!?]{0,60}[.!?]\s*|"
    r"^(we('| a)re|we are|i('| a)m|i am) (so |very |truly |deeply |super |incredibly )?"
    r"(humbled|thrilled|delighted|excited|proud|happy|glad|pleased|honou?red)( and \w+)? "
    r"to (share|announce)( that)?[,:]?\s*", re.I)
NOISE = re.compile(r"#\w+|https?://\S+|[\U0001F000-\U0001FAFF☀-➿️‍]")


def sentences(text):
    # Don't end a sentence at "Smt.", "Dr.", "Hon." and the like
    text = re.sub(r"\b(Smt|Shri|Sri|Dr|Mr|Mrs|Ms|Prof|Hon|St|No|Rs)\.\s+", lambda m: m.group(1) + ".\u00a0", text)
    return [s.replace("\u00a0", " ") for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def focus_text(title, summary, via):
    """Where the point of an item is: a news headline, or the opening of a post."""
    title = re.sub(r"^Reposted( from [^:]+)?: ", "", title)
    if via.startswith(NEWS):
        return title
    return " ".join(sentences(summary or title)[:3])[:500]


def classify(title, summary, via, employee_repost=False, media_org=False):
    """Returns (tier, kind): ("A", "Award / recognition"), ("B", "Partnership"), ("C", "Hiring / opportunity")…"""
    text = focus_text(title, summary, via)
    if ROUTINE_RE.search(f"{title} {text}"):
        return "C", "Hiring / opportunity / event"
    if employee_repost:
        return "C", "Staff post"  # an employee's own milestone, reshared by the organisation
    for kind, rx in TIER_A:
        if rx.search(text):
            return "A", kind
    if not media_org:  # a media organisation's posts describe other people's launches and partnerships
        for kind, rx in TIER_B:
            if rx.search(text):
                return "B", kind
    if via.startswith(NEWS):
        return "B", "In the news"  # third-party coverage that passed the checks is worth a look
    return "C", "Programme / general post"


def key_sentence(title, summary, via, kind=None, words=34):
    """One plain sentence saying what happened: no hashtags, emoji, publisher names or 'we are thrilled'."""
    title = re.sub(r"^Reposted( from [^:]+)?: ", "", title)
    if via.startswith(NEWS):
        candidates = [re.sub(r"\s+[-|¦–]\s+[^-|¦–]+$", "", title)]  # drop " - The Hindu"
    else:
        candidates = sentences(summary or title) or [title]
    rules = [rx for k, rx in TIER_A + TIER_B if k == kind] or [rx for _, rx in TIER_A + TIER_B]
    best = next((c for c in candidates[:6] if any(rx.search(c) for rx in rules)), candidates[0])
    best = NOISE.sub("", best)
    best = LEAD_IN.sub("", best.strip())
    best = re.sub(r"\s+", " ", best).strip(" -–:,")
    if best:
        best = best[0].upper() + best[1:]
    cut = best.rstrip("…").split()
    return " ".join(cut[:words]) + ("…" if len(cut) > words or best.endswith("…") else "")
