import io
import os
from pathlib import Path
import zipfile

from fontTools.ttLib.ttFont import TTFont
import requests

FIRA_CODE_VERSION = "6.2"
PRETENDARD_VERSION = "1.3.6"

CACHE_DIR = Path(os.path.dirname(os.path.realpath(__file__))) / ".cache"
BUILD_DIR = Path(os.path.dirname(os.path.realpath(__file__))) / "build"
FIRA_CODE_CACHE = CACHE_DIR / "fira"
PRETENDARD_CACHE = CACHE_DIR / "pretendard"

if not FIRA_CODE_CACHE.exists():
    print("Downloading Fira Code")
    os.makedirs(FIRA_CODE_CACHE)
    url = f"https://github.com/tonsky/FiraCode/releases/download/{FIRA_CODE_VERSION}/Fira_Code_v{FIRA_CODE_VERSION}.zip"
    response = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(FIRA_CODE_CACHE)

if not PRETENDARD_CACHE.exists():
    print("Downloading Pretendard")
    os.makedirs(PRETENDARD_CACHE)
    url = f"https://github.com/orioncactus/pretendard/releases/download/v{PRETENDARD_VERSION}/Pretendard-{PRETENDARD_VERSION}.zip"
    response = requests.get(url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        z.extractall(PRETENDARD_CACHE)

firacode = TTFont(FIRA_CODE_CACHE / "variable_ttf" / "FiraCode-VF.ttf")
pretendard = TTFont(PRETENDARD_CACHE / "public" / "variable" / "PretendardVariable.ttf")

result = TTFont()
result["head"] = firacode["head"]
result["hhea"] = firacode["hhea"]
result["maxp"] = firacode["maxp"]
result["OS/2"] = firacode["OS/2"]
result["hmtx"] = firacode["hmtx"]
result["cmap"] = firacode["cmap"]
result["prep"] = firacode["prep"]
result["loca"] = firacode["loca"]
result["glyf"] = firacode["glyf"]
result["name"] = firacode["name"]
result["post"] = firacode["post"]
result["gasp"] = firacode["gasp"]
result["GDEF"] = firacode["GDEF"]
result["GPOS"] = firacode["GPOS"]
result["GSUB"] = firacode["GSUB"]
result["HVAR"] = firacode["HVAR"]
result["MVAR"] = firacode["MVAR"]
result["STAT"] = firacode["STAT"]
result["avar"] = firacode["avar"]
result["fvar"] = firacode["fvar"]
result["gvar"] = firacode["gvar"]
result.setGlyphOrder(firacode.glyphOrder)

def get_gsub_feature(font, tag):
    return next((f for f in font["GSUB"].table.FeatureList.FeatureRecord if f.FeatureTag == tag), None)

def get_gsub_lookup(font, index):
    return font["GSUB"].table.LookupList.Lookup[index]

def find_substitution(font, lookup_index, backtrack, input, lookahead):
    result = []
    lookup = get_gsub_lookup(font, lookup_index)
    if lookup.LookupType == 1:
        for subtable_index, subtable in enumerate(lookup.SubTable):
            if (
                any(glyph not in subtable.mapping for glyph in backtrack) or
                any(glyph not in subtable.mapping for glyph in input) or
                any(glyph not in subtable.mapping for glyph in lookahead)
            ):
                continue
            result.append({
                "lookup": lookup_index,
                "lookup_type": lookup.LookupType,
                "subtable": subtable_index,
                "mapping": subtable.mapping
            })
    elif lookup.LookupType == 6:
        for subtable_index, subtable in enumerate(lookup.SubTable):
            if subtable.Format == 1:
                if any(glyph not in subtable.Coverage.glyphs for glyph in input):
                    continue
                for ruleset_index, ruleset in enumerate(subtable.ChainSubRuleSet):
                    for rule_index, rule in enumerate(ruleset.ChainSubRule):
                        if backtrack != list(reversed(rule.Backtrack)):
                            continue
                        # TODO: Check input
                        if lookahead != rule.LookAhead:
                            continue
                        for substitution_index, substitution in enumerate(rule.SubstLookupRecord):
                            for child in find_substitution(font, substitution.LookupListIndex, backtrack, input, lookahead):
                                result.append({
                                    "lookup": lookup_index,
                                    "lookup_type": lookup.LookupType,
                                    "subtable": subtable_index,
                                    "subtable_format": subtable.Format,
                                    "ruleset": ruleset_index,
                                    "rule": rule_index,
                                    "child": child,
                                })
            elif subtable.Format == 2:
                if any(glyph not in subtable.BacktrackClassDef.classDefs for glyph in backtrack):
                    continue
                if any(glyph not in subtable.Coverage.glyphs for glyph in input):
                    continue
                if any(glyph not in subtable.LookAheadClassDef.classDefs for glyph in lookahead):
                    continue
                backtrack_class = [subtable.BacktrackClassDef.classDefs[glyph] for glyph in backtrack]
                input_class = [subtable.InputClassDef.classDefs[glyph] for glyph in input]
                lookahead_class = [subtable.LookAheadClassDef.classDefs[glyph] for glyph in lookahead]

                for classset_index, classset in enumerate(subtable.ChainSubClassSet):
                    for rule_index, rule in enumerate(classset.ChainSubClassRule):
                        if backtrack_class != list(reversed(rule.Backtrack)):
                            continue
                        if input_class[1:] != rule.Input:
                            continue
                        if lookahead_class != rule.LookAhead:
                            continue

                        for substitution_index, substitution in enumerate(rule.SubstLookupRecord):
                            for child in find_substitution(font, substitution.LookupListIndex, backtrack, input, lookahead):
                                result.append({
                                    "lookup": lookup_index,
                                    "lookup_type": lookup.LookupType,
                                    "subtable": subtable_index,
                                    "subtable_format": subtable.Format,
                                    "classset": classset_index,
                                    "rule": rule_index,
                                    "child": child,
                                })
            elif subtable.Format == 3:
                if subtable.BacktrackGlyphCount != len(backtrack):
                    continue
                if subtable.InputGlyphCount != len(input):
                    continue
                if subtable.LookAheadGlyphCount != len(lookahead):
                    continue

                backtrack_mismatch = False
                for i in range(len(backtrack)):
                    glyph = backtrack[i]
                    coverage = subtable.BacktrackCoverage[-(i + 1)]
                    backtrack_mismatch = backtrack_mismatch or (glyph not in coverage.glyphs)
                input_mismatch = False
                for i in range(len(input)):
                    glyph = input[i]
                    coverage = subtable.InputCoverage[i]
                    input_mismatch = input_mismatch or (glyph not in coverage.glyphs)
                lookahead_mismatch = False
                for i in range(len(lookahead)):
                    glyph = lookahead[i]
                    coverage = subtable.LookAheadCoverage[i]
                    lookahead_mismatch = lookahead_mismatch or (glyph not in coverage.glyphs)

                if backtrack_mismatch or input_mismatch or lookahead_mismatch:
                    continue

                for substitution_index, substitution in enumerate(subtable.SubstLookupRecord):
                    for child in find_substitution(font, substitution.LookupListIndex, backtrack, input, lookahead):
                        result.append({
                            "lookup": lookup_index,
                            "lookup_type": lookup.LookupType,
                            "subtable": subtable_index,
                            "subtable_format": subtable.Format,
                            "substitution": substitution_index,
                            "child": child
                        })
    return result

def find_substitutions(font, feature_tag, backtrack, input, lookahead):
    result = []
    for lookup_index in get_gsub_feature(font, feature_tag).Feature.LookupListIndex:
        result += find_substitution(font, lookup_index, backtrack, input, lookahead)
    return result

def get_substitution_lookup(font, substitution_info):
    lookup = get_gsub_lookup(font, substitution_info["lookup"])
    if substitution_info["lookup_type"] == 1:
        return lookup, substitution_info
    elif substitution_info["lookup_type"] == 6:
        if substitution_info["subtable_format"] == 2:
            return get_substitution_lookup(font, substitution_info["child"])
        elif substitution_info["subtable_format"] == 3:
            return get_substitution_lookup(font, substitution_info["child"])

def find_substitution_lookups(font, feature_tag, backtrack, input, lookahead):
    result = []
    for subst in find_substitutions(font, feature_tag, backtrack, input, lookahead):
        lookup, info = get_substitution_lookup(font, subst)
        result.append((subst, lookup, info))
    return result

def replace_cmap(font, orig_glyph, new_glyph):
    for subtable in font["cmap"].tables:
        codepoint = next((k for k, v in subtable.cmap.items() if v == orig_glyph), None)
        if codepoint is not None:
            subtable.cmap[codepoint] = new_glyph

def add_lookup(font, tag, lookup_index):
    feature = get_gsub_feature(font, tag)
    lookup_list = feature.Feature.LookupListIndex
    lookup_list.append(lookup_index)
    lookup_list = list(set(lookup_list))
    lookup_list.sort()
    feature.Feature.LookupListIndex = lookup_list
    feature.Feature.LookupCount = len(lookup_list)

# Turn on cv02 by default
replace_cmap(result, "g", "g.cv02")
replace_cmap(result, "gbreve", "gbreve.cv02")
replace_cmap(result, "gcircumflex", "gcircumflex.cv02")
replace_cmap(result, "uni0123", "uni0123.cv02")
replace_cmap(result, "gdotaccent", "gdotaccent.cv02")
# Turn on ss01 by default
replace_cmap(result, "r", "r.ss01")
# Turn on ss02 by default
_, lookup, info = find_substitution_lookups(result, "calt", [], ["greater"], ["equal"])[0]
lookup.SubTable[info["subtable"]].mapping["equal"] = "greater_equal.ss02"
_, lookup, info = find_substitution_lookups(result, "calt", [], ["less"], ["equal"])[0]
lookup.SubTable[info["subtable"]].mapping["equal"] = "less_equal.ss02"
# Turn on ss03 by default
replace_cmap(result, "ampersand", "ampersand.ss03")
# TODO: sub ampersand_ampersand.liga by ampersand.ss03;
subst, _, _ = find_substitution_lookups(result, "ss03", [], ["ampersand.spacer"], ["ampersand.ss03"])[0]
add_lookup(result, "calt", subst["lookup"])
# Turn on ss05 by default
replace_cmap(result, "at", "at.ss05")
# TODO: sub asciitilde.spacer' asciitilde_at.liga by asciitilde;
# TODO: sub asciitilde asciitilde_at.liga' by at.ss05;

for codepoint in range(0xAC00, 0xD7A4):
    glyph_id = f"uni{codepoint:X}"
    result["glyf"][glyph_id] = pretendard["glyf"][glyph_id]
    result["hmtx"][glyph_id] = pretendard["hmtx"][glyph_id]
    result["gvar"].variations.data[glyph_id] = pretendard["gvar"].variations.data[glyph_id]
    for subtable in result["cmap"].tables:
        subtable.cmap[codepoint] = glyph_id

os.makedirs(BUILD_DIR, exist_ok=True)
result.save(BUILD_DIR / "PreFiraCode-VF.ttf")
