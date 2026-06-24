# scripts/gen_pyrit_taxonomy.py
"""In-container generator: enumerate PyRIT attacks and converters and write JSON snapshots.

Run inside the PyRIT container:
    python scripts/gen_pyrit_taxonomy.py

Writes:
    agentic_redteam/catalog/data/pyrit_attacks.json
    agentic_redteam/catalog/data/pyrit_converters.json
"""

import inspect
import json
import re
from collections import Counter
from pathlib import Path

import pyrit.executor.attack as _attack_mod
import pyrit.prompt_converter as _converter_mod
from pyrit.executor.attack import MultiTurnAttackStrategy, SingleTurnAttackStrategy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUT_DIR = Path("agentic_redteam/catalog/data")

# Classes to skip regardless of name matching
_SKIP_SUFFIXES = (
    "Config",
    "Context",
    "Result",
    "Printer",
    "SelectionStrategy",
)
_SKIP_EXACT = {"ConverterResult", "get_converter_modalities"}

# TAPAttack is an alias — keep only TreeOfAttacksWithPruningAttack
_ATTACK_ALIASES = {"TAPAttack"}

# Known params defaults
PARAM_DEFAULTS: dict[str, dict] = {
    "CrescendoAttack": {"max_turns": 10, "max_backtracks": 5},
}

# Known display-name overrides (applied before suffix-stripping humanization)
DISPLAY_OVERRIDES: dict[str, str] = {
    "TreeOfAttacksWithPruningAttack": "Tree of Attacks with Pruning (TAP)",
    "PAIRAttack": "PAIR",
    "ManyShotJailbreakAttack": "Many-Shot Jailbreak",
    "BargeInAttack": "Barge-In",
    "AddImageTextConverter": "Add Text to Image",
    "AddImageVideoConverter": "Add Image to Video",
    "AddTextImageConverter": "Text to Image",
    "BinAsciiConverter": "Hex (BinAscii)",
    "AsciiSmugglerConverter": "ASCII Smuggler",
    "SneakyBitsSmugglerConverter": "Sneaky Bits Smuggler",
    "VariationSelectorSmugglerConverter": "Variation Selector Smuggler",
    "LLMGenericTextConverter": "LLM Generic Rewrite",
    "ColloquialWordswapConverter": "Colloquial Word Swap",
    "MaliciousQuestionGeneratorConverter": "Malicious Question Generator",
    "ToxicSentenceGeneratorConverter": "Toxic Sentence Generator",
    "AskToDecodeConverter": "Ask to Decode",
    "NegationTrapConverter": "Negation Trap",
    "TransparencyAttackConverter": "Transparency Attack (Image)",
    "ArabiziConverter": "Arabizi (Arab Romanization)",
    "ArabicPresentationFormConverter": "Arabic Presentation Form",
    "AzureSpeechAudioToTextConverter": "Azure Speech Audio-to-Text",
    "AzureSpeechTextToAudioConverter": "Azure Speech Text-to-Audio",
    "AudioFrequencyConverter": "Audio Frequency Shift",
    "MorseConverter": "Morse Code",
    "NatoConverter": "NATO Phonetic",
    "LeetspeakConverter": "Leetspeak",
    "EcojiConverter": "Ecoji",
    "AsciiArtConverter": "ASCII Art",
    "UrlConverter": "URL Encoding",
    "CharSwapConverter": "Character Swap",
    "CharacterSpaceConverter": "Character Space",
    "RandomCapitalLettersConverter": "Random Capitals",
    "InsertPunctuationConverter": "Insert Punctuation",
    "TatweelConverter": "Tatweel (Arabic)",
    "ZalgoConverter": "Zalgo Text",
    "ZeroWidthConverter": "Zero-Width Characters",
    "UnicodeConfusableConverter": "Unicode Confusables",
    "UnicodeReplacementConverter": "Unicode Replacement",
    "UnicodeSubstitutionConverter": "Unicode Substitution",
    "BidiConverter": "Bidirectional Override",
    "FlipConverter": "Text Flip",
    "FirstLetterConverter": "First Letter Only",
    "SearchReplaceConverter": "Search and Replace",
    "TemplateSegmentConverter": "Template Segment",
    "SelectiveTextConverter": "Selective Text",
    "JsonStringConverter": "JSON String Escape",
    "AnsiAttackConverter": "ANSI Escape Attack",
    "MathObfuscationConverter": "Math Obfuscation",
    "TextJailbreakConverter": "Text Jailbreak Template",
    "MathPromptConverter": "Math Prompt",
    "DenylistConverter": "Denylist Filter",
    "NoiseConverter": "Noise Injection",
    "CodeChameleonConverter": "Code Chameleon",
    "RepeatTokenConverter": "Repeat Token",
    "SuffixAppendConverter": "Suffix Append",
    "StringJoinConverter": "String Join",
    "ImageColorSaturationConverter": "Image Color Saturation",
    "ImageCompressionConverter": "Image Compression",
    "ImageOverlayConverter": "Image Overlay",
    "ImagePromptStyleConverter": "Image Prompt Style",
    "ImageResizingConverter": "Image Resize",
    "ImageRotationConverter": "Image Rotation",
    "WordDocConverter": "Word Document",
    "ScientificTranslationConverter": "Scientific Translation",
    "RandomTranslationConverter": "Random Translation",
    "AtbashConverter": "Atbash Cipher",
    "CaesarConverter": "Caesar Cipher",
    "Base2048Converter": "Base2048",
}

# requirement overrides — for things ctor inspection can't determine reliably
REQUIREMENT_OVERRIDES: dict[str, str] = {
    # multimodal
    "AddImageTextConverter": "multimodal",
    "AddImageVideoConverter": "multimodal",
    "AddTextImageConverter": "multimodal",
    "ImageColorSaturationConverter": "multimodal",
    "ImageCompressionConverter": "multimodal",
    "ImageOverlayConverter": "multimodal",
    "ImagePromptStyleConverter": "multimodal",
    "ImageResizingConverter": "multimodal",
    "ImageRotationConverter": "multimodal",
    "TransparencyAttackConverter": "multimodal",
    "QRCodeConverter": "multimodal",
    "PDFConverter": "file",
    "WordDocConverter": "file",
    # audio
    "AudioEchoConverter": "audio",
    "AudioFrequencyConverter": "audio",
    "AudioSpeedConverter": "audio",
    "AudioVolumeConverter": "audio",
    "AudioWhiteNoiseConverter": "audio",
    # azure_service
    "AzureSpeechAudioToTextConverter": "azure_service",
    "AzureSpeechTextToAudioConverter": "azure_service",
}

# category lookup for converters (azure_service requirement maps to "azure" category)
CATEGORY_MAP: dict[str, str] = {
    # encoding
    "Base64Converter": "encoding",
    "Base2048Converter": "encoding",
    "BinAsciiConverter": "encoding",
    "BinaryConverter": "encoding",
    "AtbashConverter": "encoding",
    "CaesarConverter": "encoding",
    "ROT13Converter": "encoding",
    "MorseConverter": "encoding",
    "NatoConverter": "encoding",
    "LeetspeakConverter": "encoding",
    "BrailleConverter": "encoding",
    "EcojiConverter": "encoding",
    "EmojiConverter": "encoding",
    "AsciiArtConverter": "encoding",
    "UrlConverter": "encoding",
    # text_transform
    "StringJoinConverter": "text_transform",
    "RepeatTokenConverter": "text_transform",
    "SuffixAppendConverter": "text_transform",
    "CharSwapConverter": "text_transform",
    "CharacterSpaceConverter": "text_transform",
    "RandomCapitalLettersConverter": "text_transform",
    "InsertPunctuationConverter": "text_transform",
    "SuperscriptConverter": "text_transform",
    "DiacriticConverter": "text_transform",
    "TatweelConverter": "text_transform",
    "ZalgoConverter": "text_transform",
    "ZeroWidthConverter": "text_transform",
    "UnicodeConfusableConverter": "text_transform",
    "UnicodeReplacementConverter": "text_transform",
    "UnicodeSubstitutionConverter": "text_transform",
    "BidiConverter": "text_transform",
    "FlipConverter": "text_transform",
    "FirstLetterConverter": "text_transform",
    "ArabiziConverter": "text_transform",
    "ArabicPresentationFormConverter": "text_transform",
    "SearchReplaceConverter": "text_transform",
    "TemplateSegmentConverter": "text_transform",
    "SelectiveTextConverter": "text_transform",
    "JsonStringConverter": "text_transform",
    "AnsiAttackConverter": "text_transform",
    "MathObfuscationConverter": "text_transform",
    "TextJailbreakConverter": "text_transform",
    "MathPromptConverter": "text_transform",
    "DenylistConverter": "text_transform",
    "NoiseConverter": "text_transform",
    "CodeChameleonConverter": "text_transform",
    # smuggling
    "AsciiSmugglerConverter": "smuggling",
    "SneakyBitsSmugglerConverter": "smuggling",
    "VariationSelectorSmugglerConverter": "smuggling",
    # llm_rewrite
    "LLMGenericTextConverter": "llm_rewrite",
    "VariationConverter": "llm_rewrite",
    "TranslationConverter": "llm_rewrite",
    "RandomTranslationConverter": "llm_rewrite",
    "ScientificTranslationConverter": "llm_rewrite",
    "PersuasionConverter": "llm_rewrite",
    "TenseConverter": "llm_rewrite",
    "ToneConverter": "llm_rewrite",
    "ColloquialWordswapConverter": "llm_rewrite",
    "NegationTrapConverter": "llm_rewrite",
    "MaliciousQuestionGeneratorConverter": "llm_rewrite",
    "ToxicSentenceGeneratorConverter": "llm_rewrite",
    "AskToDecodeConverter": "llm_rewrite",
    # multimodal
    "AddImageTextConverter": "multimodal",
    "AddImageVideoConverter": "multimodal",
    "AddTextImageConverter": "multimodal",
    "ImageColorSaturationConverter": "multimodal",
    "ImageCompressionConverter": "multimodal",
    "ImageOverlayConverter": "multimodal",
    "ImagePromptStyleConverter": "multimodal",
    "ImageResizingConverter": "multimodal",
    "ImageRotationConverter": "multimodal",
    "TransparencyAttackConverter": "multimodal",
    "QRCodeConverter": "multimodal",
    # file
    "PDFConverter": "file",
    "WordDocConverter": "file",
    # audio
    "AudioEchoConverter": "audio",
    "AudioFrequencyConverter": "audio",
    "AudioSpeedConverter": "audio",
    "AudioVolumeConverter": "audio",
    "AudioWhiteNoiseConverter": "audio",
    # azure
    "AzureSpeechAudioToTextConverter": "azure",
    "AzureSpeechTextToAudioConverter": "azure",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _humanize(class_name: str, strip_suffix: str) -> str:
    if class_name in DISPLAY_OVERRIDES:
        return DISPLAY_OVERRIDES[class_name]
    name = class_name
    if name.endswith(strip_suffix):
        name = name[: -len(strip_suffix)]
    # Insert space before uppercase letters that follow lowercase letters
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    # Insert space before uppercase sequences followed by lowercase (e.g. "ROT13Converter")
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    return name.strip()


def _is_concrete(cls) -> bool:
    return isinstance(cls, type) and not inspect.isabstract(cls)


def _should_skip(name: str) -> bool:
    if name in _SKIP_EXACT:
        return True
    return any(name.endswith(suf) and name != suf for suf in _SKIP_SUFFIXES)


def _converter_requirement(class_name: str, cls) -> str:
    if class_name in REQUIREMENT_OVERRIDES:
        return REQUIREMENT_OVERRIDES[class_name]
    try:
        sig = inspect.signature(cls.__init__)
        params = sig.parameters
        if (
            "converter_target" in params
            and params["converter_target"].default is inspect.Parameter.empty
        ):
            return "llm_target"
    except (ValueError, TypeError):
        pass
    return "offline"


# ---------------------------------------------------------------------------
# Attack enumeration
# ---------------------------------------------------------------------------


def build_attacks() -> list[dict]:
    entries = []
    seen_classes: set = set()

    for name in getattr(_attack_mod, "__all__", []):
        if name in _ATTACK_ALIASES:
            continue
        if _should_skip(name):
            continue
        cls = getattr(_attack_mod, name, None)
        if cls is None or not isinstance(cls, type):
            continue
        if not name.endswith("Attack"):
            continue
        if not _is_concrete(cls):
            continue
        if cls in seen_classes:
            continue
        seen_classes.add(cls)

        if issubclass(cls, MultiTurnAttackStrategy):
            turn_type = "multi_turn"
        elif issubclass(cls, SingleTurnAttackStrategy):
            turn_type = "single_turn"
        else:
            turn_type = "meta"

        needs = {
            "multi_turn": ["adversarial_chat", "objective_scorer"],
            "single_turn": ["objective_scorer"],
            "meta": [],
        }[turn_type]

        params = PARAM_DEFAULTS.get(name, {})

        if turn_type == "meta":
            runnable = False
            runnable_reason = "Orchestration attack — select component attacks instead"
        else:
            runnable = True
            runnable_reason = ""

        entries.append(
            {
                "class_name": name,
                "display_name": _humanize(name, "Attack"),
                "turn_type": turn_type,
                "needs": needs,
                "params": params,
                "runnable": runnable,
                "runnable_reason": runnable_reason,
            }
        )

    entries.sort(key=lambda e: e["class_name"])
    return entries


# ---------------------------------------------------------------------------
# Converter enumeration
# ---------------------------------------------------------------------------


def build_converters() -> list[dict]:
    entries = []
    seen_classes: set = set()

    for name in getattr(_converter_mod, "__all__", []):
        if _should_skip(name):
            continue
        cls = getattr(_converter_mod, name, None)
        if cls is None or not isinstance(cls, type):
            continue
        if not name.endswith("Converter"):
            continue
        if not _is_concrete(cls):
            continue
        if cls in seen_classes:
            continue
        seen_classes.add(cls)

        requirement = _converter_requirement(name, cls)
        category = CATEGORY_MAP.get(name, "text_transform")

        non_runnable_requirements = {"multimodal", "audio", "file", "azure_service"}
        if requirement in non_runnable_requirements:
            runnable = False
            runnable_reason = f"Requires {requirement} infrastructure"
        else:
            runnable = True
            runnable_reason = ""

        entries.append(
            {
                "class_name": name,
                "display_name": _humanize(name, "Converter"),
                "category": category,
                "requirement": requirement,
                "runnable": runnable,
                "runnable_reason": runnable_reason,
            }
        )

    entries.sort(key=lambda e: e["class_name"])
    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    attacks = build_attacks()
    converters = build_converters()

    attacks_path = OUT_DIR / "pyrit_attacks.json"
    converters_path = OUT_DIR / "pyrit_converters.json"

    with open(attacks_path, "w", encoding="utf-8") as f:
        json.dump(attacks, f, indent=2)
    print(f"Wrote {len(attacks)} attacks -> {attacks_path}")

    with open(converters_path, "w", encoding="utf-8") as f:
        json.dump(converters, f, indent=2)
    print(f"Wrote {len(converters)} converters -> {converters_path}")

    print("\nAttacks by turn_type:")
    for k, v in sorted(Counter(a["turn_type"] for a in attacks).items()):
        print(f"  {k}: {v}")

    print("\nConverters by requirement:")
    for k, v in sorted(Counter(c["requirement"] for c in converters).items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
