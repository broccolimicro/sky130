#!/opt/python/bin/python

from lclayout.layout.layers import *
from lclayout.writer.magic_writer import MagWriter
from lclayout.writer.lef_writer import LefWriter
from lclayout.writer.gds_writer import GdsWriter
from lclayout.writer.oasis_writer import OasisWriter

import pprint
import os
import csv

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

#### These settings aren't in layout.conf

# Layer for the pins.
pin_layer = l_metal2

# Power stripe layer
power_layer = l_metal2

# Layers that can be connected/merged without changing the schematic.
# This can be used to resolve spacing/notch violations by just filling the space.
connectable_layers = {l_nwell}

# ROUTING #

# Cost for changing routing direction (horizontal/vertical).
# This will avoid creating zig-zag routings.
orientation_change_penalty = 50

# Routing edge weights per data base unit.
weights_horizontal = {
	l_poly: 15,
	l_metal1: 10,
	l_metal2: 5,
}
weights_vertical = {
	l_poly: 15,
	l_metal1: 10,
	l_metal2: 5,
}

# Via weights.
via_weights = {
	# Contacts to source/drain of transistors.
	(l_metal1, l_ndiffusion): 500,
	(l_metal1, l_pdiffusion): 500,

	# Contacts to well-taps: This weights don't matter much.
	(l_metal1, l_pplus): 1,
	(l_metal1, l_nplus): 1,

	# Vias
	(l_metal1, l_poly): 500,
	(l_metal1, l_metal2): 1000
}

# Enable double vias between layers.
multi_via = {
	(l_metal1, l_poly): 0,
	(l_metal1, l_metal2): 0,
}


#### These are loaded in through layout.conf

techName = "sky130"
actHome = os.environ.get('ACT_HOME', "/opt/cad")
layout = loadActConf(actHome + "/conf/" + techName + "/layout.conf")
prs2net = loadActConf(actHome + "/conf/" + techName + "/prs2net.conf")

# GDS2 layer numbers for final output.
layers = {
	layer: (major, minor)
	for layer, major, minor in zip(
		layout["gds"]["layers"],
		layout["gds"]["major"],
		layout["gds"]["minor"]
	)
}

# Physical size of one data base unit in meters.
# All dimensions in this file must be given in this unit.
db_unit = 5e-9
if "general" in layout:
	db_unit = layout["general"]["scale"]*1e-9

# Scale transistor width.
# Transistor dimensions are read from the SPICE netlist and assumed to have unit 'meters'.
# Based on this assumption the dimensions are automatically converted into db_units.
#
# The transistor widths as defined in the netlist can be scaled by an arbitrary factor.
# If `transistor_channel_width_sizing` is equal to 1, then no scaling is performed.
transistor_channel_width_sizing = 1

# Define how layers can be used for routing.
# Example for a layer that can be used for horizontal and vertical tracks: {'MyLayer1' : 'hv'}
# Example for a layer that can be contacted but not used for routing: {'MyLayer2' : ''}
routing_layers = {
	l_ndiffusion: '',
	l_pdiffusion: '',
	l_poly: 'hv',
	l_metal1: 'hv',
	l_metal2: 'hv',
}

# lclayout internally uses its own layer numbering scheme.
# For the final output the layers can be remapped with a mapping
# defined in this dictioinary.
matConfs = dict()
if "materials" in layout:
	matConfs = layout["materials"]
diffConfs = dict()
if "diff" in layout:
	diffConfs = layout["diff"]
viaConfs = dict()
if "vias" in layout:
	viaConfs = layout["vias"]


output_map = dict()
# TODO ACT layout conf is missing information about the outline layers
if "areaid_sc.identifier" in layers:
	output_map[l_abutment_box] = layers["areaid_sc.identifier"]

actDiffToLC = {
	"ntype": [l_ndiffusion],
	"ptype": [l_pdiffusion],
	"nfet_well": [l_pwell, l_pplus],
	"pfet_well": [l_nwell, l_nplus],
}
actMtrlToLC = {
	"polysilicon": {"": l_poly, "label": l_poly_label},
}
lcToActMtrl = dict()
actMetalsToLC = {
	"m1": (l_metal1, l_metal1_label, l_metal1_pin),
	"m2": (l_metal2, l_metal2_label, l_metal2_pin),
}
lcToActMetals = dict()
actViasToLC = {
	"polysilicon": l_poly_contact,
	"m1": l_via1,
}
lcToActVias = dict()

# Parse the 'diff' section into actMtrlToLC, actMetalsToLC, and actViasToLC
for diff, lcdiff in actDiffToLC.items():
	if diff in diffConfs and len(diffConfs[diff]) > 0:
		matConfName = diffConfs[diff][0].split(':')
		for actName, lcName in zip(matConfName, lcdiff):
			actMtrlToLC[actName] = {"": lcName}

		if diff == "ntype":
			actViasToLC[matConfName[0]] = l_ndiff_contact
		elif diff == "ptype":
			actViasToLC[matConfName[0]] = l_pdiff_contact

# Connect ACT materials, metals, and vias to Librecell
for actName, lcMap in actMtrlToLC.items():
	if actName in matConfs:
		matConf = matConfs[actName]
		if "" in lcMap:
			lcToActMtrl[lcMap[""]] = actName
		if "gds" in matConf:
			for purpose, lcName in lcMap.items():
				if len(purpose) == 0:
					output_map[lcName] = [layers[name] for name in matConf["gds"] if name in layers]
				else:
					output_map[lcName] = [layers[name.replace("drawing", purpose)] for name in matConf["gds"] if name.replace("drawing", purpose) in layers]

if "metal" in matConfs:
	metalConfs = matConfs["metal"]
	for actName, lcNames in actMetalsToLC.items():
		if actName in metalConfs:
			lcToActMetals[lcNames[0]] = metalConfs[actName]
		if f"{actName}_gds" in metalConfs:
			output_map[lcNames[0]] = [layers[name] for name in metalConfs[f"{actName}_gds"] if name in layers]
			output_map[lcNames[1]] = [layers[name.replace("drawing", "label")] for name in metalConfs[f"{actName}_gds"] if name.replace("drawing", "label") in layers]
			output_map[lcNames[2]] = [layers[name.replace("drawing", "pin")] for name in metalConfs[f"{actName}_gds"] if name.replace("drawing", "pin") in layers]

for actName, lcName in actViasToLC.items():
	if actName in viaConfs:
		lcToActVias[lcName] = viaConfs[actName]
	if f"{actName}_gds" in viaConfs:
		output_map[lcName] = [layers[name] for name in viaConfs[f"{actName}_gds"] if name in layers]

for key, value in output_map.items():
	if isinstance(value, list) and len(value) == 1:
		output_map[key] = value[0]

# Minimum spacing rules for layer pairs.
min_spacing = dict()
for lcName, actName in lcToActMtrl.items():
	if actName in matConfs and "spacing" in matConfs[actName] and len(matConfs[actName]["spacing"]) > 0:
		min_spacing[(lcName, lcName)] = matConfs[actName]["spacing"][0]

#{
#	('poly', 'poly'): 42,
#	('ndiffusion', 'ndiffusion'): 54,
#	('pdiffusion', 'pdiffusion'): 54,
#	('pplus', 'pplus'): 54,
#	('nwell', 'nwell'): 254,
#	('nplus', 'nplus'): 54,
#	('metal1', 'metal1'): 34,
#	('metal2', 'metal2'): 28
#}

min_spacing[(l_pdiffusion, l_ndiffusion)] = max(matConfs[lcToActMtrl[l_ndiffusion]]["oppspacing"][0], matConfs[lcToActMtrl[l_pdiffusion]]["oppspacing"][0])

min_spacing[(l_ndiffusion, l_poly_contact)] = matConfs[lcToActMtrl[l_ndiffusion]]["via"]["fet"]
min_spacing[(l_pdiffusion, l_poly_contact)] = matConfs[lcToActMtrl[l_ndiffusion]]["via"]["fet"]

min_spacing.update({
	(l_ndiffusion, l_pplus): 1,
	(l_pdiffusion, l_nplus): 1,
	(l_nwell, l_pplus): 1,
	(l_pwell, l_nplus): 1,
	(l_nwell, l_pwell): 1,  # This might be used when n-well and p-well layers are used for a twin-well process.
	(l_pwell, l_pwell): 1,
	(l_poly, l_nwell): 1,
	(l_poly, l_ndiffusion): 1,
	(l_poly, l_pdiffusion): 1,
	(l_poly, l_nplus): 1,
	(l_poly, l_pplus): 1,
	(l_poly, l_ndiff_contact): 1,
	(l_poly, l_pdiff_contact): 1,
})

pprint.pprint(min_spacing)

# Minimum width rules.
minimum_width = dict()
# Width of routing wires.
# This values must be larger or equal to the values in `minimum_width`.
wire_width = dict()
# Width of horizontal routing wires (overwrites `wire_width`).
wire_width_horizontal = dict()
# Minimum area rules.
min_area = dict()
if l_poly in lcToActMtrl:
	actName = lcToActMtrl[l_poly]
	if actName in matConfs and "width" in matConfs[actName]:
		minimum_width[l_poly] = matConfs[actName]["width"]
		wire_width[l_poly] = matConfs[actName]["width"]
		wire_width_horizontal[l_poly] = matConfs[actName]["width"]
	if actName in matConfs and "minarea" in matConfs[actName]:
		min_area[l_poly] = matConfs[actName]["minarea"]

if "metal" in matConfs:
	metalConfs = matConfs["metal"]
	for lcName, actName in lcToActMetals.items():
		if actName in metalConfs:
			metalConf = metalConfs[actName]
			if "spacing" in metalConf and len(metalConf["spacing"]) != 0:
				min_spacing[(lcName, lcName)] = metalConf["spacing"][0]
			if "width" in metalConf and len(metalConf["width"]) != 0:
				minimum_width[lcName] = metalConf["width"][0]
				wire_width[lcName] = metalConf["width"][0]
				wire_width_horizontal[lcName] = metalConf["width"][0]
			if "minarea" in metalConf:
				min_area[lcName] = metalConf["minarea"]

# Side lengths of vias (square shaped).
via_size = dict()
for lcName, actName in lcToActVias.items():
	if actName in viaConfs:
		viaConf = viaConfs[actName]
		if "spacing" in viaConf:
			min_spacing[(lcName, lcName)] = viaConf["spacing"]
		if "width" in viaConf:
			via_size[lcName] = viaConf["width"]

# Width of the gate polysilicon stripe, i.e. length of the transistor gate.
# This overwrites the specified gate widths in the SPICE netlist.
gate_length = 30
# gate_length_nmos = 50 # Remove comment to overwrite gate widths from SPICE netlist.
# gate_length_pmos = 50

# Minimum length a polysilicon gate must overlap the silicon.
gate_extension = 0
if "polysilicon" in matConfs:
	if "overhang" in matConfs["polysilicon"] and len(matConfs["polysilicon"]["overhang"]) != 0:
		gate_extension = matConfs["polysilicon"]["overhang"][0]

# y-offset of the transistors (active) relative to the upper or lower boundary of the cell.
# (minimal distance in y-direction from 'active' to cell boundary)
# This showed to be too tricky to choose automatically because there are following trade offs:
#   - Placing NMOS and PMOS rows closer to the center allows for shorter vertical wiring but makes the routing between the rows harder.
#   - Also this offset must be chosen in a way such that the active region actually lies on at least one routing grid point.
transistor_offset_y = 110

# Standard cell dimensions.
# A 'unit cell' corresponds to the dimensions of the smallest possible cell. Usually an inverter.
# `unit_cell_width` also corresponds to the pitch of the gates because gates are spaced on a regular grid.
unit_cell_width = 170 # 138 # 94 # 276
unit_cell_height = 544

# Routing pitch
routing_grid_pitch_x = unit_cell_width // 2
routing_grid_pitch_y = unit_cell_height // 9

# Translate routing grid such that the bottom left grid point is at (grid_offset_x, grid_offset_y)
grid_offset_x = routing_grid_pitch_x
grid_offset_y = routing_grid_pitch_y // 2


# y coordinates of the grid.
grid_ys = list(range(grid_offset_y, grid_offset_y + unit_cell_height, routing_grid_pitch_y))

# Width of power rail.
power_rail_width = 96

# Minimum gate widths of transistors, i.e. minimal widths of l_ndiffusion and l_pdiffusion.
minimum_gate_width_nfet = 0
if "nfet" in layout["diff"] and len(layout["diff"]["nfet"]) != 0:
	actName = layout["diff"]["nfet"][0]
	if actName in matConfs:
		if "width" in matConfs[actName]:
			minimum_gate_width_nfet = matConfs[actName]["width"]

minimum_gate_width_pfet = 0
if "pfet" in layout["diff"] and len(layout["diff"]["pfet"]) != 0:
	actName = layout["diff"]["pfet"][0]
	if actName in matConfs:
		if "width" in matConfs[actName]:
			minimum_gate_width_pfet = matConfs[actName]["width"]

# Minimum width for pins.
minimum_pin_width = 0
if pin_layer in lcToActMetals and "width" in metalConfs[lcToActMetals[pin_layer]]:
	minimum_pin_width = metalConfs[lcToActMetals[pin_layer]]["width"]


dn = {
	l_ndiff_contact: [l_ndiffusion, l_nplus],
	l_pdiff_contact: [l_pdiffusion, l_pplus],
	l_poly_contact: [l_poly],
	l_via1: [l_metal1],
}
up = {
	l_ndiff_contact: [l_metal1],
	l_pdiff_contact: [l_metal1],
	l_poly_contact: [l_metal1],
	l_via1: [l_metal2],
}
# Minimum enclosure rules.
# Syntax: {(outer layer, inner layer): minimum enclosure, ...}
minimum_enclosure = {
	# Via enclosure
	(l_ndiffusion, l_ndiff_contact): 0,
	(l_pdiffusion, l_pdiff_contact): 0,
	(l_nplus, l_ndiff_contact): 0,  # Implicitly encodes the size of well taps.
	(l_pplus, l_pdiff_contact): 0,  # Implicitly encodes the size of well taps.
	(l_nwell, l_nplus): 0,
	(l_pwell, l_pplus): 0,
	(l_poly, l_poly_contact): 0,
	(l_metal1, l_ndiff_contact): 0,
	(l_metal1, l_pdiff_contact): 0,
	(l_metal1, l_poly_contact): 0,
	(l_metal1, l_via1): 0,
	(l_metal2, l_via1): 0,

	# l_nwell must overlap l_pdiffusion.
	(l_nwell, l_pdiffusion): 0,
	# l_pwell must overlap l_ndiffusion.
	(l_pwell, l_ndiffusion): 0
}

print(lcToActVias)

for lcName, actName in lcToActVias.items():
	if actName in viaConfs and "surround" in viaConfs[actName]:
		surround = viaConfs[actName]["surround"]
		print(actName, lcName, surround)
		if lcName in up:
			for u in up[lcName]:
				minimum_enclosure[(u, lcName)] = surround["asym_up"]
		if lcName in dn:
			for d in dn[lcName]:
				minimum_enclosure[(d, lcName)] = surround["asym_dn"]

if l_nwell in lcToActMtrl and lcToActMtrl[l_nwell] in matConfs:
	minimum_enclosure[(l_nwell, l_pdiffusion)] = matConfs[lcToActMtrl[l_nwell]]["overhang"]

if l_pwell in lcToActMtrl and lcToActMtrl[l_pwell] in matConfs:
	minimum_enclosure[(l_pwell, l_pdiffusion)] = matConfs[lcToActMtrl[l_pwell]]["overhang"]

pprint.pprint(minimum_enclosure)

# Minimum notch rules.
minimum_notch = {
	l_ndiffusion: 0,
	l_pdiffusion: 0,
	l_poly: 0,
	l_metal1: 0,
	l_metal2: 0,
	l_nwell: 0
}

# Define a list of output writers.
output_writers = [
	GdsWriter(
		db_unit=db_unit,
		output_map=output_map
	),
]
