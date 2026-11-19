"""Linguistic cues of instructions aimed at the AI rather than facts about the document.

Each cue has a weight; the score is a noisy-OR of matched cue weights, in [0, 1].
Bare trigger words ("override", "ignore", "instructions") are NOT cues on their own.

ling-v2 adds Hinglish, Hindi-script and Telugu-script cues (MULTILINGUAL_CUES). Each one
translates an English cue family below; imperative verb forms are required where the English
cue needs a command. A policy can switch them off (`linguistic.multilingual: false`) and add
domain cues (`linguistic.extra_cues`, used by domain adapters) without code changes.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

VERSION = "ling-v2"

_AI = r"(?:ai|a\.i\.|assistant|chatbot|language model|llm|model|screener|reviewer bot|bot)"
_PRIOR = r"(?:all |any |the |your |my )*(?:previous|prior|above|earlier|preceding|original|other)"
_RULES = r"(?:instructions?|prompts?|rules|guidelines|directions|context|content|criteria)"

CUES: list[tuple[str, float, str]] = [
    ("ignore_previous", 0.90, rf"\b(?:ignore|disregard|forget|skip|bypass)\b[^.]{{0,20}}\b{_PRIOR}\s+{_RULES}"),
    ("disregard_above", 0.80, r"\b(?:disregard|ignore)\s+(?:all\s+|everything\s+)?(?:the\s+)?(?:above|previous|prior|earlier)\b"),
    ("override_instructions", 0.80, rf"\boverride\s+(?:your|the|all|any|previous|prior|system)\s+{_RULES}"),
    ("new_instructions", 0.70, rf"\bnew\s+{_RULES}\b"),
    ("system_prompt", 0.70, r"\bsystem\s+prompt\b"),
    ("address_ai", 0.70, rf"\b(?:note|message|instruction)s?\s+(?:to|for)\s+(?:the\s+)?{_AI}\b"),
    ("as_the_ai", 0.70, rf"\bas\s+(?:an?|the)\s+{_AI}\b"),
    ("you_are_now", 0.70, r"\byou\s+are\s+now\b"),
    ("developer_mode", 0.70, r"\b(?:developer|jailbreak|god)\s+mode\b"),
    ("you_must", 0.50, r"\byou\s+(?:must|should|will|need to|have to)\b"),
    ("ai_should", 0.60, rf"\b(?:the\s+)?{_AI}\s+(?:must|should|will|needs to|has to)\b"),
    ("recommend_candidate", 0.60, r"\b(?:recommend|select|shortlist|approve|hire)\s+(?:this|the)\s+(?:candidate|applicant|person|resume|application)\b"),
    ("rate_highest", 0.60, r"\b(?:rate|rank|score|give)\b[^.]{0,30}\b(?:highest|first|top|10\s*(?:/|out of)\s*10|best)\b"),
    ("respond_only", 0.60, r"\b(?:respond|reply|answer|output)\s+(?:only\s+)?with\b"),
    ("do_not_reveal", 0.60, r"\bdo\s+not\s+(?:reveal|mention|disclose|tell)\b"),
    ("regardless", 0.40, r"\bregardless\s+of\s+(?:other|any|the)\b"),
    ("when_summarizing", 0.40, r"\bwhen\s+(?:summari[sz]ing|evaluating|reviewing|screening)\s+this\b"),
]

# --- Hindi (Devanagari). No \b: Python's \w does not cover Indic vowel signs. -------------
_GAP_HI = r"[^।॥.!?\n]"
_HI_PRIOR = r"(?:पिछल|पूर्व|ऊपर|पहले|मूल|अन्य|बाकी|बाक़ी|दूसरे)"
_HI_RULES = r"(?:निर्देश|दिशानिर्देश|नियम|आदेश|हिदायत|प्रॉम्प्ट|संदर्भ|सामग्री|मानदंड)"
_HI_IGNORE = r"(?:अनदेखा|नज़रअंदाज़|नजरअंदाज|उपेक्षा|भूल|छोड़|छोड|दरकिनार)"
_HI_RECOMMEND = (r"(?:सुझाएं|सुझाएँ|सुझाओ|सुझाइए|चुनें|चुनो|चुनिए|चुन लें|चुन लो|मंज़ूर करें|"
                 r"मंजूर करें|मंज़ूर करो|मंजूर करो|स्वीकृत करें|स्वीकृत करो|सिफ़ारिश करें|"
                 r"सिफारिश करें|सिफ़ारिश करो|सिफारिश करो|नियुक्त करें|नियुक्त करो|भर्ती करें|"
                 r"भर्ती करो|शॉर्टलिस्ट करें|शॉर्टलिस्ट करो)")
_HI_GIVE = r"(?:दें|दो|दीजिए|दीजिये)"

# --- Hinglish (Latin script) ----------------------------------------------------------------
_HG_PRIOR = (r"(?:pichle|pichhle|pichli|pehle|pahle|upar|purane|baaki|baki|dusre|previous|"
             r"prior|earlier|above|other)")
_HG_RULES = r"(?:instructions?|rules?|guidelines?|niyam|nirdesh|criteria|prompts?|directions?)"
_HG_IGNORE = r"(?:ignore|bhool|bhul|nazarandaz|nazar\s*andaz|chhod|chod|skip|bypass)"
_HG_DO = r"(?:karo|kar do|kijiye|karein|karen|karna|kar dena)"

# --- Telugu ---------------------------------------------------------------------------------
_GAP_TE = r"[^.!?\n]"
_TE_PRIOR = r"(?:మునుపటి|ఇంతకు ముందు|ఇంతకుముందు|పై|గత|అసలు|ఇతర|మిగతా|మిగిలిన)"
_TE_RULES = r"(?:సూచన|నియమ|మార్గదర్శక|ఆదేశ|ప్రమాణ|ప్రాంప్ట్)"
_TE_IGNORE = (r"(?:విస్మరించ|పట్టించుకోవద్దు|పట్టించుకోకండి|మర్చిపో|మరచిపో|వదిలేయ|వదిలి|"
              r"దాటవేయ)")
_TE_SUBJECT = r"ఈ\s*(?:అభ్యర్థి|దరఖాస్తు|రెజ్యూమే|వ్యక్తి)"
_TE_RECOMMEND = r"(?:సిఫార్సు\s*చేయ|ఎంపిక\s*చేయ|ఆమోదించ|నియమించ|షార్ట్‌లిస్ట్\s*చేయ)(?:ండి|ు|ి)"

MULTILINGUAL_CUES: list[tuple[str, float, str]] = [
    # Hindi
    ("ignore_previous_hi", 0.90, rf"{_HI_PRIOR}{_GAP_HI}{{0,40}}{_HI_RULES}{_GAP_HI}{{0,30}}{_HI_IGNORE}"),
    ("new_instructions_hi", 0.70, r"नए\s+(?:निर्देश|नियम)"),
    ("system_prompt_hi", 0.70, r"सिस्टम\s*(?:प्रॉम्प्ट|प्रोम्प्ट|प्रांप्ट)"),
    ("address_ai_hi", 0.70, r"(?:एआई|AI|सहायक|मॉडल|बॉट|चैटबॉट)\s*(?:के लिए|को)\s*(?:नोट|संदेश|निर्देश|सूचना)"),
    ("you_are_now_hi", 0.70, r"(?:आप|तुम)\s+अब\s|अब\s+(?:आप|तुम)\s"),
    ("you_must_hi", 0.50, rf"(?:आपको|तुम्हें|तुमको){_GAP_HI}{{0,30}}(?:करना होगा|करना चाहिए|करना है)"),
    ("recommend_candidate_hi", 0.60, rf"(?:इस|इसे|इन्हें){_GAP_HI}{{0,40}}{_HI_RECOMMEND}"),
    ("rate_highest_hi", 0.60, rf"(?:सबसे\s*(?:ऊँची|ऊंची|अधिक|ज़्यादा|ज्यादा|अच्छी|अच्छा|बेहतर)|सर्वोच्च|सर्वाधिक|शीर्ष){_GAP_HI}{{0,25}}{_HI_GIVE}"),
    ("do_not_reveal_hi", 0.60, r"(?:खुलासा|प्रकट|ज़ाहिर|जाहिर|उल्लेख|ज़िक्र|जिक्र)\s*(?:न|मत)\s*(?:करें|करो|करना|कीजिए|करिए)|(?:न|मत)\s*(?:बताएं|बताएँ|बताओ|बताना|बताइए)"),
    ("when_summarizing_hi", 0.40, r"(?:सारांश|मूल्यांकन|समीक्षा|स्क्रीनिंग)\s*(?:बनाते|करते)\s*समय"),
    # Hinglish
    ("ignore_previous_hinglish", 0.90, rf"\b{_HG_PRIOR}\b[^.!?\n]{{0,30}}\b{_HG_RULES}\b[^.!?\n]{{0,25}}\b{_HG_IGNORE}"),
    ("new_instructions_hinglish", 0.70, rf"\b(?:naye|nayi|naya)\s+{_HG_RULES}\b"),
    ("address_ai_hinglish", 0.70, r"\b(?:ai|model|assistant|bot|chatbot)\s+(?:ke liye|ko)\s+(?:note|message|sandesh|instructions?)\b"),
    ("you_are_now_hinglish", 0.70, r"\b(?:ab\s+(?:tum|aap)|(?:tum|aap)\s+ab)\b"),
    ("you_must_hinglish", 0.50, r"\b(?:tumhe|tumhein|tumko|aapko|apko)\b[^.!?\n]{0,30}\b(?:karna hoga|karna chahiye|karna hai|karna padega)\b"),
    ("recommend_candidate_hinglish", 0.60, rf"\b(?:is|iss|ise|isko|isse)\b[^.!?\n]{{0,30}}\b(?:recommend|select|shortlist|approve|hire)\s*{_HG_DO}\b"),
    ("rate_highest_hinglish", 0.60, r"\b(?:sabse|sab se)\s+(?:high|zyada|jyada|achhi|acchi|accha|best|top)\b[^.!?\n]{0,25}\b(?:do|de do|dena|dijiye)\b"),
    ("do_not_reveal_hinglish", 0.60, r"\b(?:reveal|disclose|mention|batana|batao|bataiye|zikr)\s+(?:mat|na|nahi)\b|\b(?:mat|na)\s+(?:batana|batao|bataiye|reveal|mention|disclose)\b"),
    ("when_summarizing_hinglish", 0.40, r"\b(?:summari[sz]e|evaluate|review|screen|screening)\s+karte\s+(?:waqt|samay|time)\b"),
    # Telugu
    ("ignore_previous_te", 0.90, rf"{_TE_PRIOR}{_GAP_TE}{{0,40}}{_TE_RULES}{_GAP_TE}{{0,40}}{_TE_IGNORE}"),
    ("new_instructions_te", 0.70, r"కొత్త\s+(?:సూచన|నియమ|ఆదేశ)"),
    ("system_prompt_te", 0.70, r"సిస్టమ్\s*ప్రాంప్ట్"),
    ("address_ai_te", 0.70, r"(?:ఏఐ|ఎఐ|AI|సహాయకుడ|మోడల్|బాట్)[^\s.]{0,4}\s*(?:కోసం|కు)?\s*(?:గమనిక|సందేశం)"),
    ("you_are_now_te", 0.70, r"(?:మీరు|నువ్వు)\s+ఇప్పుడు"),
    ("you_must_te", 0.50, rf"(?:మీరు|నువ్వు){_GAP_TE}{{0,30}}(?:తప్పక|తప్పనిసరిగా)"),
    ("recommend_candidate_te", 0.60, rf"{_TE_SUBJECT}{_GAP_TE}{{0,40}}{_TE_RECOMMEND}"),
    ("rate_highest_te", 0.60, rf"(?:అత్యధిక|అత్యుత్తమ|అత్యున్నత|అగ్ర)\s*(?:రేటింగ్|స్కోర్|మార్కులు|ర్యాంక్){_GAP_TE}{{0,15}}(?:ఇవ్వండి|ఇవ్వు|ఇవ్వాలి)"),
    ("do_not_reveal_te", 0.60, r"(?:బహిర్గతం|వెల్లడి|చెప్ప|ప్రస్తావించ|తెలియజేయ)\s*(?:చేయ)?(?:వద్దు|కండి|కూడదు)"),
    ("when_summarizing_te", 0.40, r"(?:సారాంశం|మూల్యాంకనం|సమీక్ష|స్క్రీనింగ్)[^.\n]{0,15}(?:చేస్తున్నప్పుడు|చేసేటప్పుడు)"),
]

Cue = tuple[str, float, re.Pattern]


def _compile(cues) -> tuple[Cue, ...]:
    # Patterns and text are both NFKC-normalized (canonical text is NFKC; nukta letters
    # such as ज़ decompose under NFKC).
    return tuple((name, float(w), re.compile(unicodedata.normalize("NFKC", p), re.IGNORECASE))
                 for name, w, p in cues)


_COMPILED = _compile(CUES)
_MULTILINGUAL = _compile(MULTILINGUAL_CUES)


@lru_cache(maxsize=32)
def _cue_set(multilingual: bool, extra: tuple[tuple[str, float, str], ...]) -> tuple[Cue, ...]:
    return _COMPILED + (_MULTILINGUAL if multilingual else ()) + _compile(extra)


def cues_for(policy: dict[str, Any] | None) -> tuple[Cue, ...]:
    """Cue set for a policy: English, plus multilingual (default on), plus domain extra_cues."""
    cfg = (policy or {}).get("linguistic") or {}
    extra = tuple((str(c["name"]), float(c["weight"]), str(c["pattern"]))
                  for c in cfg.get("extra_cues") or [])
    return _cue_set(bool(cfg.get("multilingual", True)), extra)


def version_for(policy: dict[str, Any] | None) -> str:
    cfg = (policy or {}).get("linguistic") or {}
    v = VERSION if cfg.get("multilingual", True) else f"{VERSION} (english only)"
    n = len(cfg.get("extra_cues") or [])
    return f"{v}+{n} policy cues" if n else v


@dataclass
class LinguisticResult:
    score: float
    cues: list[str] = field(default_factory=list)


def score_text(text: str, cues: tuple[Cue, ...] | None = None) -> LinguisticResult:
    """`cues`: from cues_for(policy); default is English + multilingual cues."""
    text = unicodedata.normalize("NFKC", text)
    miss = 1.0
    found = []
    for name, weight, pattern in (_cue_set(True, ()) if cues is None else cues):
        if pattern.search(text):
            found.append(name)
            miss *= 1.0 - weight
    return LinguisticResult(round(1.0 - miss, 4), found)
