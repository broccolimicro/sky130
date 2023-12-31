#!/usr/bin/python3

# docs/rules/layers/

import csv
from datetime import datetime
import os
import pwd
import re

indent = 0
def attr(kind, name, value):
	global indent
	print("	"*indent + kind + " " + name + " " + (("\"" + str(value) + "\"") if kind == "string" else str(value)))

def table(kind, name, tbl):
	global indent
	print("	"*indent + kind + "_table " + name + " " + " ".join(["\"" + str(col) + "\"" for col in tbl] if kind == "string" else [str(col) for col in tbl]))

def begin(name):
	global indent
	print("	"*indent + "begin " + name)
	indent += 1

def end():
	global indent
	indent -= 1
	print("	"*indent + "end")
	print("")

def getCreator():
	return pwd.getpwuid(os.getuid())[4]

def getDate():
	return datetime.today().strftime('%b %d, %Y')

def getTech():
	return os.path.basename(os.getcwd())

def dedupName(layers, name):
	layerSet = set(layers)
	result = name
	idx = 0
	while result in layerSet:
		idx += 1
		result = name + str(idx)
	return result

def toCamelCase(s, c=r' '):
	return re.sub(c + r'([a-z])', lambda m: m.group(1).upper(), s.strip().lower())

def createPurposes(col, purposeMap):
	purposes = [toCamelCase(c) for c in col.split(",")]
	return purposes
	#return [purposeMap[p][0] for p in purposes if p in purposeMap]
	
def createLayerName(name, purposes, layers):
	name = toCamelCase(name)
	if purposes:
		name += "." + purposes[0]
	return dedupName(layers, name)

def isMetalLayer(name, purposes):
	return "dg" in purposes and re.match(r'(met|li)[0-9]*$', name)

def getPurposeMap():
	purposeMap = dict()
	with open("pdk/docs/rules/layers/table-c4a-layer-description.csv", "r") as fptr:
		rd = csv.reader(fptr, delimiter=",", quotechar="\"")
		for number, row in enumerate(rd):
			if number > 0:
				purposeMap[row[0].strip()] = (row[1].strip(),row[2].strip())
	return purposeMap

def getGDS(purposeMap):
	layers = []
	major = []
	minor = []
	metals = []
	drawing = []
	idSet = set()

	with open("pdk/docs/rules/gds_layers.csv", "r") as fptr:
		rd = csv.reader(fptr, delimiter=",", quotechar="\"")
		for number, row in enumerate(rd):
			if number > 0 and row[2] != "" and row[2] not in idSet:
				idSet.add(row[2])
				purposes = createPurposes(row[1], purposeMap)
				name = createLayerName(row[0], purposes, layers)
				layer, datatype = row[2].split(":")

				layers.append(name)
				major.append(layer)
				minor.append(datatype)
				if isMetalLayer(row[0], purposes):
					metals.append(name)

	return (layers, major, minor, metals)

def getDeviceLayers():
	layerStart = 4
	layerEnd = -1
	with open("pdk/docs/rules/layers/table-f2b-mask.tsv", "r") as fptr:
		rd = csv.reader(fptr, delimiter="\t", quotechar="\"")
		for number, row in enumerate(rd):
			row = [col.strip() for col in row]
			if number == 0:
				layerNames = [layer.lower() for layer in row[layerStart:layerEnd]]
			else:
				if row[0].lower() in ["resistor", "capacitor", "inductor", "diode"]:
					pass
				elif "cmos" in row[0].lower():
					model = row[3]
					layers = [layer for layer, state in zip(layerNames, row[layerStart:layerEnd]) if state == 'C']
					print(model, layers)

#def getTechFile():
#	with open("pdk/libraries/sky130_fd_pr/latest/tech/sky130_fd_pr.tlef", "r") as fptr:
#		for number, row in enumerate(fptr):
			

begin("info")
attr("string", "name", getTech())
attr("string", "date", "Created on " + getDate() + " by " + getCreator())
end()

purposeMap = getPurposeMap()
layers, major, minor, metals = getGDS(purposeMap)

begin("general")
attr("real", "scale", 75) # nm
attr("int", "metals", len(metals))
attr("int", "stacked_contacts", 1)
attr("int", "welltap_adjust", 0)
end()

begin("gds")
table("string", "layers", layers)
table("int", "major", major)
table("int", "minor", minor)
end()

#diff

#poly

#nwell
#dnwell "deep nwell"

#./sky130_fd_sc_hs/latest/cells/tapvpwrvgnd/sky130_fd_sc_hs__tapvpwrvgnd_1.lef

flavors = ["svt"]#, "lvt", "hvt", "mvt", "v10", "v5n"]

begin("diff")
table("string", "types", flavors)
table("string", "ptype", [f+"pdiff" for f in flavors])
table("string", "ntype", [f+"ndiff" for f in flavors])
table("string", "pfet", [f+"ppoly" for f in flavors])
table("string", "pfet_well", [f+"nwell:"+f+"ntap" for f in flavors])
table("string", "nfet", [f+"npoly" for f in flavors])
table("string", "nfet_well", [":"+f+"ptap" for f in flavors])
end()


