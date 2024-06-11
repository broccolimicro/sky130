# Skywater 130nm PDK

This is the single source of truth for the PDK configuration files. You may
clone this to your personal computer with the following command line:

```
cd /opt/tech
git clone https://github.com/broccolimicro/sky130.git
cd sky130
git submodule update --init --recursive
```

## Regenerating cells.act

If `spi2act.py` is updated or you need to regenerate `cells.act` for any other
reason, then you may do so using the following commands.

```
./script/find_cells.sh
spi2act.py prs2net.conf cells.spice > cells.act
```
