from datetime import datetime
import io
from itertools import chain
import math
import os
from pathlib import Path
import zipfile

from fontTools.ttLib.ttFont import TTFont
import requests

FONT_VERSION = "1.000"

FIRA_CODE_VERSION = "6.2"
PRETENDARD_VERSION = "1.3.6"
CREATED_AT = datetime.strptime("2023-02-13 12:00:00", "%Y-%m-%d %H:%M:%S")
MODIFIED_AT = datetime.strptime("2023-02-13 12:00:00", "%Y-%m-%d %H:%M:%S")

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

def find_name(font, nameID):
    return next(name.string.decode("utf_16_be") for name in font["name"].names if name.nameID == nameID)

def encode_name(platformID, value):
    if platformID == 3:
        return value.encode("utf_16_be")
    else:
        return bytes(value, "utf_8")

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

result["head"].fontRevision = float(FONT_VERSION)
result["head"].created = int(CREATED_AT.timestamp() - datetime.strptime("1904-01-01 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp())
result["head"].modified = int(MODIFIED_AT.timestamp() - datetime.strptime("1904-01-01 00:00:00", "%Y-%m-%d %H:%M:%S").timestamp())

# TODO: head.xMin, yMIn, xMax, yMax
# TODO: head.indexToLocFormat
# TODO: hhea.ascent, descent
# TODO: hhea.advanceWidthMax,
# TODO: hhea.minLeftSideBearing, minRightSideBearing
# TODO: hhea.xMaxExtent
# TODO: hhea.numberOfHMetrics
# TODO: maxp.numGlyphs
# TODO: maxp.maxPoints
# TODO: maxp.maxContours
# TODO: maxp.maxCompositePoints
# TODO: maxp.maxCompositeContours
# TODO: maxp.maxTwilightPoints
# TODO: maxp.maxStorage
# TODO: maxp.maxFunctionDefs
# TODO: maxp.maxStackElements
# TODO: maxp.maxComponentElements
# TODO: maxp.maxComponentDepth
# TODO: OS/2.xAvgCharWidth
# TODO: OS/2.usWeightClass
# TODO: OS/2.ySubscriptXSize, ySubscriptYSize, ySubscriptYOffset
# TODO: OS/2.ySuperscriptXSize, ySuperscriptYSize, ySuperscriptYOffset
# TODO: OS/2.yStrikeoutSize, yStrikeoutPosition
# # TODO: OS/2.panose
# TODO: OS/2.ulUnicodeRange1, ulUnicodeRange2, ulUnicodeRange3, ulUnicodeRange4
# TODO: OS/2.achVendID
# TODO: OS/2.usFirstCharIndex
# TODO: OS/2.sTypoAscender, sTypoDescender
# TODO: OS/2.winAscent, winDescent
# TODO: OS/2.ulCodePageRange1, ulCodePageRange2
# TODO: OS/2.sxHeight, sCapHeight
# TODO: OS/2.usMaxContext
for name in result["name"].names:
    if name.nameID == 0:
        firacode_copyright = find_name(firacode, 0)
        pretendard_copyright = find_name(pretendard, 0)
        name.string = encode_name(name.platformID, f"FiraCode - {firacode_copyright}, Pretendard - {pretendard_copyright}")
    if name.nameID == 1:
        name.string = encode_name(name.platformID, "PreFira Code Variable")
    elif name.nameID == 2:
        name.string = encode_name(name.platformID, "Regular")
    elif name.nameID == 3:
        name.string = encode_name(name.platformID, f"{FONT_VERSION};CTRM;PreFiraCodeVariable")
    elif name.nameID == 4:
        name.string = encode_name(name.platformID, "PreFira Code Variable")
    elif name.nameID == 5:
        name.string = encode_name(name.platformID, f"Version {FONT_VERSION}")
    elif name.nameID == 6:
        name.string = encode_name(name.platformID, "PreFiraCodeVariable-Regular")
    elif name.nameID == 7:
        firacode_trademark = find_name(firacode, 7)
        pretendard_trademark = find_name(pretendard, 7)
        name.string = encode_name(name.platformID, f"FiraCode - {firacode_trademark}, Pretendard - {pretendard_trademark}")
    elif name.nameID == 8:
        firacode_manufacturer = find_name(firacode, 8)
        pretendard_manufacturer = find_name(pretendard, 8)
        name.string = encode_name(name.platformID, f"{firacode_manufacturer}, {pretendard_manufacturer}, Joonmo Yang")
    elif name.nameID == 9:
        firacode_designer = find_name(firacode, 9)
        pretendard_designer = find_name(pretendard, 9)
        name.string = encode_name(name.platformID, f"FiraCode - {firacode_designer}; Pretendard - {pretendard_designer}")
    elif name.nameID == 11:
        name.string = encode_name(name.platformID, "https://github.com/remagpie/PreFiraCode")
    elif name.nameID == 12:
        name.string = encode_name(name.platformID, "https://github.com/remagpie/PreFiraCode")
    elif name.nameID == 13:
        name.string = encode_name(name.platformID, "This Font Software is licensed under the SIL Open Font License, Version 1.1. This license is available with a FAQ at: http://scripts.sil.org/OFL")
    elif name.nameID == 14:
        name.string = encode_name(name.platformID, "http://scripts.sil.org/OFL")
    elif name.nameID == 16:
        name.string = encode_name(name.platformID, "PreFira Code Variable")
    elif name.nameID == 17:
        name.string = encode_name(name.platformID, "Regular")
    elif name.nameID == 25:
        name.string = encode_name(name.platformID, "PreFiraCode Variable")
    elif name.nameID == 262:
        name.string = encode_name(name.platformID, "PreFiraCode-Light")
    elif name.nameID == 263:
        name.string = encode_name(name.platformID, "PreFiraCode-Regular")
    elif name.nameID == 264:
        name.string = encode_name(name.platformID, "PreFiraCode-Medium")
    elif name.nameID == 265:
        name.string = encode_name(name.platformID, "PreFiraCode-SemiBold")
    elif name.nameID == 266:
        name.string = encode_name(name.platformID, "PreFiraCode-Bold")

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

# Calculate glyph scaling factor with letter M
fira_M = firacode["glyf"]["M"]
pretendard_M = pretendard["glyf"]["M"]
glyph_scale = (fira_M.yMax - fira_M.yMin) / (pretendard_M.yMax - pretendard_M.yMin)

# Calculate delta scaling factor
fira_weight = next(axis for axis in firacode["fvar"].axes if axis.axisTag == "wght")
pretendard_weight = next(axis for axis in pretendard["fvar"].axes if axis.axisTag == "wght")
delta_scale = fira_weight.maxValue / pretendard_weight.maxValue
## 0.8 is magical value for fitting thickness
delta_scale = delta_scale * glyph_scale * 0.8

# Insert hangul characters
pretendard["gvar"].ensureDecompiled()
for codepoint in chain(range(0x3131, 0x3163), range(0xAC00, 0xD7A4)):
    glyph_id = f"uni{codepoint:X}"
    glyph = pretendard["glyf"][glyph_id]
    glyph.coordinates = glyph.coordinates.copy()
    glyph.coordinates.scale((glyph_scale, glyph_scale))
    glyph.xMin = math.inf
    glyph.xMax = -math.inf
    glyph.yMin = math.inf
    glyph.yMax = -math.inf
    for i in range(0, len(glyph.coordinates.array), 2):
        glyph_x = round(glyph.coordinates.array[i])
        glyph_y = round(glyph.coordinates.array[i + 1])
        glyph.coordinates.array[i] = glyph_x
        glyph.coordinates.array[i + 1] = glyph_y
        glyph.xMin = min(glyph.xMin, glyph_x)
        glyph.xMax = max(glyph.xMax, glyph_x)
        glyph.yMin = min(glyph.yMin, glyph_y)
        glyph.yMax = max(glyph.yMax, glyph_y)
    result["glyf"][glyph_id] = glyph
    result["hmtx"][glyph_id] = pretendard["hmtx"][glyph_id]

    variation = pretendard["gvar"].variations.data[glyph_id]
    for v in variation:
        for i in range(len(v.coordinates)):
            coordinate = v.coordinates[i]
            if coordinate != None:
                v.coordinates[i] = (round(coordinate[0] * delta_scale), round(coordinate[1] * delta_scale))
    result["gvar"].variations.data[glyph_id] = variation
    for subtable in result["cmap"].tables:
        subtable.cmap[codepoint] = glyph_id

# print(result["OS/2"].__dict__)
# print(firacode["OS/2"].__dict__)
# print(pretendard["OS/2"].__dict__)

os.makedirs(BUILD_DIR, exist_ok=True)
result.save(BUILD_DIR / "PreFiraCode-VF.ttf")
result.saveXML(BUILD_DIR / "asdf.xml")
