# KLayout (version 0.28 or higher) technology files for Skywater 130nm

 * sky130.lyt   : technology and connections description
 * sky130.lyp   : layers color and shape description
 * drc/drc_sky130.lydrc : DRC script
 * lvs/lvs_sky130.lylvs : LVS script  (coming soon, so far only for MOSfet)
 * def-lef/layermap.txt : layermap for the import_def.rb file : need to add in the config.mk file a line :
`export GDS_LAYER_MAP = ../../../../$(PLATFORM_DIR)/layermap.txt`

To configure, place a symbolic link to this repo from your `~/.klayout/tech` folder

The DRC/LVS files have not been extensively tested.

