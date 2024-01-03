#!/usr/bin/python3

import os
import sys
import copy

import csv

import lxml.etree
import lxml.builder
import pprint

def isIn(searches, string):
	for search in searches:
		if search in string:
			return True
	return False

def startsWithAny(searches, string):
	for search in searches:
		if string.startswith(search):
			return True
	return False

def splitLayerID(layerID):
	name = layerID
	purpose = ""
	if "." in name:
		name, purpose = layerID.rsplit(".", 1)
	return name, purpose

def purposeToID(purpose):
	if purpose in ["drawing", "dg", "drw"]:
		return "dg"
	elif purpose in ["pin", "pn"]:
		return "pn"
	elif purpose in ["boundary", "by", "bnd"]:
		return "by"
	elif purpose in ["net", "nt"]:
		return "nt"
	elif purpose in ["res", "rs"]:
		return "rs"
	elif purpose in ["label", "ll", "lbl"]:
		return "ll"
	elif purpose in ["cut", "ct"]:
		return "ct"
	elif purpose in ["short", "st", "sho"]:
		return "st"
	elif purpose in ["gate", "ge", "gat"]:
		return "ge"
	elif purpose in ["probe", "pe", "pro"]:
		return "pe"
	elif purpose in ["blockage", "be", "blo"]:
		return "be"
	elif purpose in ["model", "ml", "mod"]:
		return "ml"
	elif startsWithAny(["option", "o", "opt"], purpose):
		return "o"
	elif purpose in ["fuse", "fe", "fus"]:
		return "fe"
	elif purpose in ["mask", "mk"]:
		return "mk"
	elif purpose in ["maskAdd", "md"]:
		return "md"
	elif purpose in ["maskDrop", "mp"]:
		return "mp"
	elif startsWithAny(["waffleAdd", "w"], purpose):
		return "w"		
	elif purpose in ["waffleDrop", "wp", "waf"]:
		return "wp"
	elif purpose in ["error", "er", "err"]:
		return "er"
	elif purpose in ["warning", "wg", "wng"]:
		return "wg"
	elif purpose in ["dummy", "dy", "dmy"]:
		return "dy"
	else:
		return "no"

def parseLine(line):
	result = list(csv.reader([line.strip()], delimiter=' ', quotechar='"'))[0]
	for i, elem in enumerate(result):
		if elem.startswith("#"):
			result = result[0:i]
			break

	return [elem.strip() for elem in result if elem.strip()]

def loadActConf(path):
	result = dict()
	stack = [result]
	with open(path, "r") as fptr:
		for number, line in enumerate(fptr):
			args = parseLine(line)
			if len(args) > 0:
				if args[0] == "include":
					result = result | loadActConf(args[1])
				elif args[0] == "begin":
					stack[-1][args[1]] = dict()
					stack.append(stack[-1][args[1]])
				elif args[0] == "end":
					stack.pop()
				elif args[0] == "string":
					stack[-1][args[1]] = args[2]
				elif args[0] == "int":
					stack[-1][args[1]] = int(args[2])
				elif args[0] == "real":
					stack[-1][args[1]] = float(args[2])
				elif args[0] == "int_table":
					stack[-1][args[1]] = [int(arg) for arg in args[2:]]
				elif args[0] == "string_table":
					stack[-1][args[1]] = args[2:]
	return result

def writeLayerMap(path, conf):
	# See https://github.com/KLayout/klayout/blob/766dd675c11d98b2461c448035197f6e934cb497/src/plugins/streamers/lefdef/db_plugin/dbLEFDEFImporter.cc#L1085
	# Purpose Name = Placement Code
	# LEFPIN			 = LEFPIN
	# PIN					= PIN
	# LEFPINNAME	 = LEFLABEL
	# PINNAME			= LABEL
	# FILL				 = FILL
	# FILLOPC			= FILLOPC
	# LEFOBS			 = OBS
	# SPNET				= SPNET
	# NET					= NET
	# VIA					= VIA
	# BLOCKAGE		 = BLK
	# ALL = [LEFPIN, PIN, FILL, FILLOPC, OBS, SPNET, NET, VIA]
	layers = zip(conf["gds"]["layers"], conf["gds"]["major"], conf["gds"]["minor"])
	with open(path, "w") as fptr:
		for layer in layers:
			name, purpose = splitLayerID(layer[0])
			if purpose in ["drawing", "dg", "drw"]:
				print(f"{name} LEFOBS,FILL,FILLOPC,VIA {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["label", "ll", "lbl"]:
				print(f"NAME {name}/PINNAME {layer[1]} {layer[2]}", file=fptr)
				print(f"NAME {name}/PIN {layer[1]} {layer[2]}", file=fptr)
				print(f"NAME {name}/LEFPINNAME {layer[1]} {layer[2]}", file=fptr)
				print(f"NAME {name}/LEFPIN {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["net", "nt"]:
				print(f"{name} NET,SPNET {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["pin", "pin1", "pn"]:
				print(f"{name} PIN,LEFPIN {layer[1]} {layer[2]}", file=fptr)
			elif purpose in ["blockage", "block", "be", "blo"]:
				print(f"{name} BLOCKAGE {layer[1]} {layer[2]}", file=fptr)
			if name.lower().startswith("areaid") and name.lower().endswith("sc"):
				print(f"DIEAREA ALL {layer[1]} {layer[2]}", file=fptr)

class Parser(object):
	def __init__(self):
		self.syntax = dict()
		# key -> value
		self.stack = [("", self.syntax)]

	def start(self, tag, attrs):
		insert = dict()
		if self.stack:
			if tag in self.stack[-1][1]:
				if isinstance(self.stack[-1][1][tag], list):
					self.stack[-1][1][tag].append(insert)
				else:
					self.stack[-1][1][tag] = [
						self.stack[-1][1][tag],
						insert
					]
			else:
				self.stack[-1][1][tag] = insert
		self.stack.append((tag, insert))

	def end(self, tag):
		if tag == self.stack[-1][0]:
			self.stack.pop()

	def data(self, data):
		if self.stack and data.strip():
			if len(self.stack) > 1 and isinstance(self.stack[-1][1], dict) and not self.stack[-1][1]:
				if isinstance(self.stack[-2][1][self.stack[-1][0]], list):
					self.stack[-2][1][self.stack[-1][0]][-1] = data
				else:
					self.stack[-2][1][self.stack[-1][0]] = data
			elif isinstance(self.stack[-1][1], str):
				self.stack[-2][1][self.stack[-1][0]] += data
			else:
				print("syntax error", self.stack, data)

	def close(self):
		return self

def readKLayoutConf(path):
	parser = lxml.etree.XMLParser(target = Parser())
	with open(path, "r") as fptr:
		parser.feed(fptr.read())
	return parser.close().syntax	
	
def buildKLayoutConf(conf, e=lxml.builder.ElementMaker(), key=None):
	result = []
	if isinstance(conf, dict):
		for key, value in conf.items():
			if not isinstance(value, list):
				value = [value]
			result += buildKLayoutConf(value, e, key)
	elif isinstance(conf, list):
		for item in conf:
			child = e(key)
			elems = buildKLayoutConf(item, e)
			for elem in elems:
				if isinstance(elem, lxml.etree._Element):
					child.append(elem)
				elif elem is not None:
					if isinstance(elem, bool):
						child.text = str(elem).lower()
					else:
						child.text = str(elem)
			result.append(child)
	else:
		result.append(conf)
	return result

def writeKLayoutConf(path, conf):
	with open(path, "wb") as fptr:
		klays = buildKLayoutConf(conf)
		for klay in klays:
			fptr.write(lxml.etree.tostring(klay, encoding='utf-8', xml_declaration=True, pretty_print=True))

def createLYTFromACT(prs2net, layout, actHome):
	lyt = readKLayoutConf("default.lyt")
	
	layers = {
		layer: (major, minor)
		for layer, major, minor in zip(
			layout["gds"]["layers"],
			layout["gds"]["major"],
			layout["gds"]["minor"]
		)
	}
	layerMap = "layer_map(" + ";".join([
			f"'{layer} : {gds[0]}/{gds[1]}'"
			for layer, gds in layers.items()
		]) + ")"
	techName = layout["info"]["name"]
	dbu = float(layout["general"]["scale"])*1e-3

	# build the tech file (lyt)
	if "technology" not in lyt:
		lyt["technology"] = dict()

	lyt["technology"] |= {
		"name": techName,
		"description": layout["info"]["date"],
		"dbu": dbu,
		"base-path": f"{actHome}/conf/{techName}/klayout",
		"layer-properties_file": f"{techName}.lyp",
	}

	if "reader-options" not in lyt["technology"]:
		lyt["technology"]["reader-options"] = dict()

	if "common" not in lyt["technology"]["reader-options"]:
		lyt["technology"]["reader-options"]["common"] = dict()

	# LEFDEF Layer Purposes
	# from https://github.com/KLayout/klayout/blob/6c8d97adc97bf992ccbdb5f7950cb95a28ffeab9/src/plugins/streamers/lefdef/db_plugin/dbLEFDEFImporter.h#L1037
	# Routing              from DEF only
  # Pins                 from DEF
  # Fills                from DEF
  # FillsOPC             from DEF
  # SpecialRouting       from DEF only
  # LEFPins              from LEF
  # ViaGeometry          from LEF+DEF
  # Label                from DEF
  # LEFLabel             from LEF
  # Obstructions         from LEF only
  # Outline              from LEF+DEF
  # Blockage             from DEF only
  # PlacementBlockage    from DEF only
  # Regions              from DEF only
  # RegionsNone          from DEF only
  # RegionsFence         from DEF only
  # RegionsGuide         from DEF only
  # All                  from DEF only
	if "lefdef" not in lyt["technology"]["reader-options"]:
		lyt["technology"]["reader-options"]["lefdef"] = dict()

	lyt["technology"]["reader-options"]["lefdef"] |= {
		"layer-map": layerMap,
		"dbu": dbu,

		# these options are not part of the technology, but are specific to the cell placer
		"produce-placement-blockages": True,
		"placement-blockage-layer": "place.block", # tell the placer to avoid placing cells in an area
		"produce-regions": True,
		"region-layer": "place.mask", # tell the placer to put cells in an area
	
		"produce-net-names": True,
		#"net-property-name": "#23", # guessing this is the gds datatype of the *.net layers?
		"produce-inst-names": True,
		#"inst-property-name": "#1", # TODO dump standard cell gds and look for "shape properties"
		"produce-pin-names": True,
		#"pin-property-name": "#1",

		"produce-cell-outlines": True,
		"cell-outline-layer": "areaid_sc.identifier",

		"produce-via-geometry": True,
		"via-geometry-suffix-string": ".drawing",
		#"via-geometry-datatype-string": None,

		"produce-pins": True,
		"pins-suffix-string": ".pin",
		#"pins-datatype-string": None,
		"produce-lef-pins": True,
		"lef_pins-suffix-string": ".pin",
		#"lef_pins-datatype-string": None,		

		"produce-fills": True,
		"fills-suffix-string": ".drawing",
		#"fills-datatype-string": None,

		"produce-obstructions": True,
		"obstructions-suffix": ".drawing",
		#"obstructions-datatype": None,

		"produce-blockages": True,
		"blockages-suffix": ".block",
		#"blockages-datatype": None,

		"produce-labels": True,
		"labels-suffix": ".label",
		#"labels-datatype": None,
		"produce-lef-labels": True,
		"lef-labels-suffix": ".label",
		#"lef-labels-datatype": None,

		"produce-routing": True,
		"routing-suffix-string": ".drawing",
		#"routing-datatype-string": None,
		"produce-special-routing": True,
		"special-routing-suffix-string": ".drawing",
		#"special-routing-datatype-string": None,
		"via-cellname-prefix": None,
		"lef-files": None,
	}

	if "mebes" not in lyt["technology"]["reader-options"]:
		lyt["technology"]["reader-options"]["mebes"] = dict()

	if "dxf" not in lyt["technology"]["reader-options"]:
		lyt["technology"]["reader-options"]["dxf"] = dict()

	lyt["technology"]["reader-options"]["dxf"] |= {
		"dbu": dbu,
		"unit": round(prs2net["net"]["lambda"]*1e6/dbu),
	}

	if "cif" not in lyt["technology"]["reader-options"]:
		lyt["technology"]["reader-options"]["cif"] = dict()

	lyt["technology"]["reader-options"]["cif"] |= {
		"dbu": dbu,
	}

	if "mag" not in lyt["technology"]["reader-options"]:
		lyt["technology"]["reader-options"]["mag"] = dict()

	lyt["technology"]["reader-options"]["mag"] |= {
		"dbu": dbu,
		"lambda": round(prs2net["net"]["lambda"]*1e6/dbu),
	}

	if "connectivity" not in lyt["technology"]:
		lyt["technology"]["connectivity"] = dict()

	matMap = dict()
	for name, mat in layout["materials"].items():
		if isinstance(mat, dict) and "gds" in mat:
			if name not in matMap:
				matMap[name] = []
			matMap[name] += [layers[layer] for layer in mat["gds"] if layer in layers]

	metMap = list()
	for name, met in layout["materials"]["metal"].items():
		if name.startswith("m") and name.endswith("_gds"):
			mid = int(name[1:-4])
			if len(metMap) <= mid:
				metMap += [[]]*(mid+1-len(metMap))
			metMap[mid] += [layers[layer] for layer in met if layer in layers]

	if len(matMap)+len(metMap) > 0:
		if "symbols" not in lyt["technology"]["connectivity"]:
			lyt["technology"]["connectivity"]["symbols"] = list()	

		for name, mat in matMap.items():
			lyt["technology"]["connectivity"]["symbols"].append(
				f"{name}='" + "+".join(f"{gds[0]}/{gds[1]}" for gds in mat) + "'"
			)

		for mid, met in enumerate(metMap):
			lyt["technology"]["connectivity"]["symbols"].append(
				f"m{mid}='" + "+".join(f"{gds[0]}/{gds[1]}" for gds in met) + "'"
			)

	if "connection" not in lyt["technology"]["connectivity"]:
		lyt["technology"]["connectivity"]["connection"] = list()
	for name, via in layout["vias"].items():
		if name.endswith("_gds"):
			dn = name[0:-4]
			up = "m1"
			if dn.startswith("m") and dn[1:].isdigit():
				up = int(dn[1:])+1

			viaMap = [layers[layer] for layer in via if layer in layers]
			lyt["technology"]["connectivity"]["connection"].append(
				f"{dn}," + "+".join(f"{gds[0]}/{gds[1]}" for gds in viaMap) + f",{up}"
			)

	#pprint.pprint(lyt)
	return lyt

def createLYPFromACT(layout, actHome):
	lyp = readKLayoutConf("default.lyp")
	
	userPurpose = ["dg", "pn", "ll", "er", "wg"]
	userLayers = ["areaid_sc.identifier", "text.drawing"]
	layers = [(layer, major, minor, purposeToID(splitLayerID(layer)[1]))
		for layer, major, minor in zip(layout["gds"]["layers"], layout["gds"]["major"], layout["gds"]["minor"])]
	layers = sorted([
		layer for layer in layers if layer[0] in userLayers], key=lambda x: (x[1], -x[2])) + sorted([
		layer for layer in layers if layer[3] in userPurpose and layer[0] not in userLayers], key=lambda x: (x[1], -x[2])) + [
		layer for layer in layers if layer[3] not in userPurpose and layer[0] not in userLayers
	]

	
	# build the properties file (lyp)
	if "layer-properties" not in lyp:
		lyp["layer-properties"] = dict()

	defaultProperties = dict()
	if "properties" in lyp["layer-properties"]:
		defaultProperties = lyp["layer-properties"]["properties"]
	lyp["layer-properties"]["properties"] = []

	ndiffs = set()
	for diff in layout["diff"]["ntype"]:
		if diff in layout["materials"] and "gds" in layout["materials"][diff]:
			ndiffs.update(layout["materials"][diff]["gds"])
	for well in layout["diff"]["pfet_well"]:
		well = well.split(":")[1]
		if len(well) > 0 and well in layout["materials"] and "gds" in layout["materials"][well]:
			ndiffs.update(layout["materials"][well]["gds"])

	pdiffs = set()
	for diff in layout["diff"]["ptype"]:
		if diff in layout["materials"] and "gds" in layout["materials"][diff]:
			pdiffs.update(layout["materials"][diff]["gds"])
	for well in layout["diff"]["nfet_well"]:
		well = well.split(":")[1]
		if len(well) > 0 and well in layout["materials"] and "gds" in layout["materials"][well]:
			pdiffs.update(layout["materials"][well]["gds"])
	diffs = ndiffs & pdiffs
	ndiffs = list(ndiffs - diffs)
	pdiffs = list(pdiffs - diffs)
	diffs = list(diffs)

	diffsSupport = [splitLayerID(layer)[0] for layer in diffs]
	ndiffsSupport = [splitLayerID(layer)[0] for layer in ndiffs]
	pdiffsSupport = [splitLayerID(layer)[0] for layer in pdiffs]

	pwells = set()
	for well in layout["diff"]["nfet_well"]:
		well = well.split(":")[0]
		if len(well) > 0 and well in layout["materials"] and "gds" in layout["materials"][well]:
			pwells.update(layout["materials"][well]["gds"])

	nwells = set()
	for well in layout["diff"]["pfet_well"]:
		well = well.split(":")[0]
		if len(well) > 0 and well in layout["materials"] and "gds" in layout["materials"][well]:
			nwells.update(layout["materials"][well]["gds"])
	wells = nwells & pwells
	nwells = list(nwells - wells)
	pwells = list(pwells - wells)
	wells = list(wells)

	wellsSupport = [splitLayerID(layer)[0] for layer in wells]
	nwellsSupport = [splitLayerID(layer)[0] for layer in nwells]
	pwellsSupport = [splitLayerID(layer)[0] for layer in pwells]

	poly = set()
	if "polysilicon" in layout["materials"] and "gds" in layout["materials"]["polysilicon"]:
		poly = set(layout["materials"]["polysilicon"]["gds"])
	poly = list(poly)	
	polySupport = [splitLayerID(layer)[0] for layer in poly]

	metals = list()
	if "metals" in layout["general"] and "metal" in layout["materials"]:
		for mid in range(0, layout["general"]["metals"]):
			key = f"m{mid+1}_gds"
			if key in layout["materials"]["metal"]:
				metals.append(layout["materials"]["metal"][key])
	metalsSupport = [[splitLayerID(layer)[0] for layer in metal] for metal in metals]
	metalCol = ["#0000ff", "#ff0080", "#ffa900", "#d700ff", "#00feff", "#13ff00"]
	metalDith = ["I6", "I4", "I8", "I4", "I8", "I4"]
	metalSupportDith = ["I10", "I8", "I4", "I8", "I4", "I8"]

	viaDiffs = set()
	if "vias" in layout:
		for diff in layout["diff"]["ntype"]:
			if f"{diff}_gds" in layout["vias"]:
				viaDiffs.update(layout["vias"][f"{diff}_gds"])
		for diff in layout["diff"]["ptype"]:
			if f"{diff}_gds" in layout["vias"]:
				viaDiffs.update(layout["vias"][f"{diff}_gds"])
		for well in layout["diff"]["nfet_well"]:
			well = well.split(":")[1]
			if len(well) > 0 and f"{well}_gds" in layout["vias"]:
				viaDiffs.update(layout["vias"][f"{well}_gds"])
		for well in layout["diff"]["pfet_well"]:
			well = well.split(":")[1]
			if len(well) > 0 and f"{well}_gds" in layout["vias"]:
				viaDiffs.update(layout["vias"][f"{well}_gds"])
	viaDiffs = list(viaDiffs)
	viaDiffsSupport = [splitLayerID(layer)[0] for layer in viaDiffs]

	viaWells = set()
	if "vias" in layout:
		for well in layout["diff"]["nfet_well"]:
			well = well.split(":")[0]
			if len(well) > 0 and f"{well}_gds" in layout["vias"]:
				viaWells.update(layout["vias"][f"{well}_gds"])
		for well in layout["diff"]["pfet_well"]:
			well = well.split(":")[0]
			if len(well) > 0 and f"{well}_gds" in layout["vias"]:
				viaWells.update(layout["vias"][f"{well}_gds"])
	viaWells = list(viaWells)
	viaWellsSupport = [splitLayerID(layer)[0] for layer in viaWells]

	vias = list()
	if "metals" in layout["general"] and "vias" in layout:
		for mid in range(0, layout["general"]["metals"]-1):
			key = f"m{mid+1}_gds"
			if key in layout["vias"]:
				vias.append(layout["vias"][key])
	viasSupport = [[splitLayerID(layer)[0] for layer in via] for via in vias]
	viaCol = ["#aaaaff", "#ff9acd", "#ffe1a6", "#f2abff", "#b6ffff", "#c9ffc4"]

	for layer, major, minor, purpose in layers:
		properties = copy.deepcopy(defaultProperties)
		name, purposeFull = splitLayerID(layer)

		properties |= {
			"name": f"{layer} - {major}/{minor}",
			"source": f"{major}/{minor}",
			"visible": purpose in userPurpose or layer in userLayers,
		}

		if purpose == "er":
			properties |= {
				"frame-color": "#ff0000",
				"fill-color": "#ff0000",
				"dither-pattern": "blank",
				"line-style": "C",
				"xfill": True,
			}
		elif purpose == "wg":
			properties |= {
				"frame-color": "#ffff00",
				"fill-color": "#ffff00",
				"dither-pattern": "blank",
				"line-style": "C0",
				"xfill": True,
			}
		elif layer in diffs:
			idx = diffs.index(layer)
			properties |= {
				"frame-color": "#ffc280",
				"fill-color": "#ffc280",
				"dither-pattern": "I2",
				"line-style": "C0",
			}
		elif layer in ndiffs:
			idx = ndiffs.index(layer)
			properties |= {
				"frame-color": "#80a8ff",
				"fill-color": "#80a8ff",
				"dither-pattern": "I3",
				"line-style": "C0",
			}
		elif layer in pdiffs:
			idx = pdiffs.index(layer)
			properties |= {
				"frame-color": "#ff9d9d",
				"fill-color": "#ff9d9d",
				"dither-pattern": "I3",
				"line-style": "C0",
			}
		elif layer in wells:
			idx = wells.index(layer)
			properties |= {
				"frame-color": "#ffc280",
				"fill-color": "#ffc280",
				"dither-pattern": "I1",
				"line-style": "C0",
			}
		elif layer in nwells:
			idx = nwells.index(layer)
			properties |= {
				"frame-color": "#ff0000",
				"fill-color": "#ff0000",
				"dither-pattern": "I1",
				"line-style": "C0",
			}
		elif layer in pwells:
			idx = pwells.index(layer)
			properties |= {
				"frame-color": "#0000ff",
				"fill-color": "#0000ff",
				"dither-pattern": "I1",
				"line-style": "C0",
			}
		elif layer in poly:
			idx = poly.index(layer)
			properties |= {
				"frame-color": "#01ff6b",
				"fill-color": "#01ff6b",
				"dither-pattern": "I2",
				"line-style": "C0",
			}
		elif layer in set(sum(metals, [])):
			for mid, met in enumerate(metals):
				if layer in met:
					idx = met.index(layer)
					properties |= {
						"frame-color": metalCol[mid%len(metalCol)],
						"fill-color": metalCol[mid%len(metalCol)],
						"dither-pattern": metalDith[mid%len(metalDith)],
						"line-style": "C0",
					}
		elif layer in set(sum(vias, [])):
			for vid, via in enumerate(vias):
				if layer in via:
					idx = via.index(layer)
					properties |= {
						"frame-color": viaCol[vid%len(viaCol)],
						"fill-color": viaCol[vid%len(viaCol)],
						"dither-pattern": "I0",
						"line-style": "C0",
					}
		elif layer in viaDiffs:
			idx = viaDiffs.index(layer)
			properties |= {
				"frame-color": "#ffffff",
				"fill-color": "#ffffff",
				"dither-pattern": "I0",
				"line-style": "C0",
			}
		elif layer in viaWells:
			idx = viaWells.index(layer)
			properties |= {
				"frame-color": "#aaffff",
				"fill-color": "#aaffff",
				"dither-pattern": "I0",
				"line-style": "C0",
			}
		elif purpose == "ll":
			properties |= {
				"frame-color": "#ffffff",
				"fill-color": "#ffffff",
				"dither-pattern": "I0",
				"line-style": "C0",
			}
		elif name in diffsSupport:
			idx = diffsSupport.index(name)
			properties |= {
				"frame-color": "#ffc280",
				"fill-color": "#ffc280",
				"dither-pattern": "I0",
				"line-style": "C0",
			}
		elif name in ndiffsSupport:
			idx = ndiffsSupport.index(name)
			properties |= {
				"frame-color": "#80a8ff",
				"fill-color": "#80a8ff",
				"dither-pattern": "I2",
				"line-style": "C0",
			}
		elif name in pdiffsSupport:
			idx = pdiffsSupport.index(name)
			properties |= {
				"frame-color": "#ff9d9d",
				"fill-color": "#ff9d9d",
				"dither-pattern": "I2",
				"line-style": "C0",
			}
		elif name in wellsSupport:
			idx = wellsSupport.index(name)
			properties |= {
				"frame-color": "#ffc280",
				"fill-color": "#ffc280",
				"dither-pattern": "I3",
				"line-style": "C0",
			}
		elif name in nwellsSupport:
			idx = nwellsSupport.index(name)
			properties |= {
				"frame-color": "#ff0000",
				"fill-color": "#ff0000",
				"dither-pattern": "I3",
				"line-style": "C0",
			}
		elif name in pwellsSupport:
			idx = pwellsSupport.index(name)
			properties |= {
				"frame-color": "#0000ff",
				"fill-color": "#0000ff",
				"dither-pattern": "I3",
				"line-style": "C0",
			}
		elif name in polySupport:
			idx = polySupport.index(name)
			properties |= {
				"frame-color": "#01ff6b",
				"fill-color": "#01ff6b",
				"dither-pattern": "I0",
				"line-style": "C0",
			}
		elif name in viaDiffsSupport:
			idx = viaDiffsSupport.index(name)
			properties |= {
				"frame-color": "#000000",
				"fill-color": "#ffffff",
				"dither-pattern": "I1",
				"line-style": "C0",
			}
		elif name in viaWellsSupport:
			idx = viaWellsSupport.index(name)
			properties |= {
				"frame-color": "#000000",
				"fill-color": "#aaffff",
				"dither-pattern": "I1",
				"line-style": "C0",
			}
		elif name in set(sum(metalsSupport, [])):
			for mid, met in enumerate(metalsSupport):
				if name in met:
					idx = met.index(name)
					properties |= {
						"frame-color": metalCol[mid%len(metalCol)],
						"fill-color": metalCol[mid%len(metalCol)],
						"dither-pattern": metalSupportDith[mid%len(metalDith)],
						"line-style": "C0",
					}
		elif name in set(sum(viasSupport, [])):
			for vid, via in enumerate(viasSupport):
				if name in via:
					idx = via.index(name)
					properties |= {
						"frame-color": viaCol[vid%len(viaCol)],
						"fill-color": viaCol[vid%len(viaCol)],
						"dither-pattern": "I0",
						"line-style": "C0",
					}
		else:
			pass
			
		lyp["layer-properties"]["properties"].append(properties)

	#pprint.pprint(lyp)
	return lyp
	
def print_help():
	print("Usage: generate_klayout_tech.py [options]")
	print("\t-T<tech>\tidentify the technology used for this translation.")

if __name__ == "__main__":
	if len(sys.argv) >= 2 and (sys.argv[1] == '--help' or sys.argv[1] == '-h'):
		print_help()
	else:
		techName = "sky130"
		actHome = os.environ.get('ACT_HOME', "/opt/cad")
		for arg in sys.argv[1:]:
			if arg[0] == '-':
				if arg[1] == 'T':
					techName = arg[2:]
				else:
					print(f"error: unrecognized option '{arg}'")
					print("")
					print_help()
					sys.exit()

		layout = loadActConf(actHome + "/conf/" + techName + "/layout.conf")
		prs2net = loadActConf(actHome + "/conf/" + techName + "/prs2net.conf")
		writeKLayoutConf(f"{techName}.lyt", createLYTFromACT(prs2net, layout, actHome))
		writeKLayoutConf(f"{techName}.lyp", createLYPFromACT(layout, actHome))
		writeLayerMap("layermap.txt", layout)
